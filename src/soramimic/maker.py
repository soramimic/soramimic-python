# 移植元: frontend/src/lib/soramimic.js
"""soramimic.js からの移植(ロジック無改変)。

SoramimiMaker: 発音の類似度に基づく DP で、各行の入力読みに近い単語列を割り当てる。
JSの setTimeout 連鎖は同期 for ループに置き換え、戻り値は results(行ごとの単語リストの
リスト)を返す(意図的な API 改善)。
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Sequence
from operator import itemgetter
from typing import Any

from .kana_similarity import KanaSimilarity, SimTable
from .text_analyzer import TextAnalyzer
from .utils import find_min, js_object_key_order

Token = dict[str, Any]
Word = dict[str, Any]

INF = float("inf")

# DPに常設する「filler(万能候補)」1ユニットあたりのコスト(#128)。
# fillerは「その位置の元歌詞のかなをそのまま置く」仮想語で、単語が足りない・
# どの単語も合わない区間を必ず埋められる。実単語が1つでも置けるなら必ず負ける
# だけの巨大な有限値にすることで、単語が足りている行の結果は従来と完全に同一になる。
#
# 値の根拠(実単語の1行あたり総コストの上限):
#   ・ユニット距離: 類似度行列の最大値は80(母音×2r・子音×2(1-r)にスケールしても
#     ベースの (子音+母音)/2 の最大は80のまま)。重みは行内で平均1に正規化される
#     =総和がユニット数なので、行全体でも 80×ユニット数 を超えない
#   ・VARIATION_COST(既定16・UI最大18)×変種操作数
#   ・WORD_NUMBER_PENALTY(UI最大60)・MID_PHRASE_BREAK_PENALTY(UI最大160)×単語数
# 1行は最長40文字(本体 convert.js の MAX_PHRASE_LENGTH)なのでユニット数も40程度で、
# 上記を全部足しても1万台に収まる。1e6 はその2桁上なので「fillerを1つ減らせる
# 経路は必ず安い」が成り立ち、かつ 1e6×ユニット数 でも倍精度の整数精度(2^53)には
# 遠く届かないため、スコアの丸めで順序が壊れることもない
FILLER_COST = 1e6

logger = logging.getLogger(__name__)

_SIM_KEY = itemgetter("sim")
_MISSING = object()


def _column_sums(rvs: list[list[float]], icols: list[list[int]], n: int) -> list[float]:
    """ユニット位置ごとの距離を、バケツ内の全単語ぶんまとめて足し込む。

    rvs[i][j]  : 候補の位置 i のユニットと、ユニットid j のカナとの距離
    icols[i][k]: バケツの k 番目の単語の、位置 i のユニットid

    返すのは各単語の合計距離で、``_ld`` が単語ごとに ``score += kana_dist[c[i]][p[i]]``
    と積み上げるのと同じ値になる。``x + r0[a] + r1[b] + ...`` は左結合で評価される
    ので加算の順序も 0.0, 位置0, 位置1, ... のままで、浮動小数の丸めまで一致する。
    1回の内包表記で最大4位置ぶんまとめるのは、中間リストの生成と zip の往復を減らす
    ためだけの措置(位置ごとに1回ずつ回すより約2倍速い)。
    """
    totals = [0.0] * n
    i = 0
    length = len(rvs)
    while i < length:
        rest = length - i
        if rest >= 4:
            r0, r1, r2, r3 = rvs[i], rvs[i + 1], rvs[i + 2], rvs[i + 3]
            c0, c1, c2, c3 = icols[i], icols[i + 1], icols[i + 2], icols[i + 3]
            totals = [
                x + r0[a] + r1[b] + r2[c] + r3[d]
                for x, a, b, c, d in zip(totals, c0, c1, c2, c3, strict=True)
            ]
            i += 4
        elif rest == 3:
            r0, r1, r2 = rvs[i], rvs[i + 1], rvs[i + 2]
            c0, c1, c2 = icols[i], icols[i + 1], icols[i + 2]
            totals = [
                x + r0[a] + r1[b] + r2[c] for x, a, b, c in zip(totals, c0, c1, c2, strict=True)
            ]
            i += 3
        elif rest == 2:
            r0, r1 = rvs[i], rvs[i + 1]
            c0, c1 = icols[i], icols[i + 1]
            totals = [x + r0[a] + r1[b] for x, a, b in zip(totals, c0, c1, strict=True)]
            i += 2
        else:
            r0, c0 = rvs[i], icols[i]
            totals = [x + r0[a] for x, a in zip(totals, c0, strict=True)]
            i += 1
    return totals


class _WordlistIndex:
    """単語DB(ユニット数 → 単語リスト)を get_similar_word 用に前処理したもの。

    get_similar_word の内側は「候補(歌詞側の発音バリエーション)× 単語DBの1バケツ」
    という総当たりで、うっせぇわ×駅名(9,467行)では距離計算が2千万回近く走る。
    そこを単語ごとの Python ループではなく「ユニット位置ごとの列」をまとめて回す
    形に変えるため、バケツごとに次を1度だけ作って使い回す。

      * prons   : 単語ごとの発音(ユニット列)
      * vcosts  : 単語ごとの変種コスト
      * icols   : 位置 i のユニットidを全単語ぶん並べた列(prons の転置)

    ユニットidは kana_dist のキーの並び順で振った通し番号で、距離の引き当てを
    「辞書をカナ文字列で引く」から「リストを整数で引く」に置き換えるためのもの。
    kana_dist に載っていないユニットには末尾の予備id(_unit_ids の要素数)を割り当て、
    行ベクトル側でそこを Infinity にしておく。_ld が未知ユニットで Infinity を返すのと
    同じ結果になり、そういう単語が数語混ざっているだけでバケツ全体が遅い経路に
    落ちるのを防げる(学者リストなどで実際に起きる)。

    icols は「全単語のユニット数がバケツのキーと一致する」ときだけ作る。
    一致しないバケツ(_ld が長さ不一致で Infinity を返す)は None にして、
    従来どおり _ld を単語ごとに呼ぶ。

    kana_dist を握るのは icols・行ベクトルが kana_dist に依存するため。1回の generate の
    間 kana_dist は不変なので、インデックスは generate_from_tokens で1つ作って使い回す。
    """

    __slots__ = (
        "wordlist",
        "kana_dist",
        "_unit_ids",
        "_row_values",
        "_cache",
        "_orders",
    )

    def __init__(self, wordlist: dict[int, list[Word]], kana_dist: SimTable) -> None:
        self.wordlist = wordlist
        self.kana_dist = kana_dist
        self._unit_ids = {u: i for i, u in enumerate(kana_dist)}
        self._row_values: dict[str, list[float] | None] = {}
        self._cache: dict[int, tuple[list[Any], list[int], list[list[int]] | None]] = {}
        self._orders: dict[tuple[str, ...], list[str]] = {}

    def bucket(self, key: int) -> tuple[list[Any], list[int], list[list[int]] | None]:
        entry = self._cache.get(key)
        if entry is None:
            words = self.wordlist[key]
            prons = [w["pronunciation"] for w in words]
            vcosts = [w.get("vcost") or 0 for w in words]
            unit_ids = self._unit_ids
            unknown = len(unit_ids)  # kana_dist に無いユニット用の予備id
            icols: list[list[int]] | None = None
            if all(len(p) == key for p in prons):
                get = unit_ids.get
                icols = [[get(p[i], unknown) for p in prons] for i in range(key)]
            entry = (prons, vcosts, icols)
            self._cache[key] = entry
        return entry

    def row_values(self, unit: str) -> list[float] | None:
        """ユニット unit から見た距離を、ユニットid順に並べたリストで返す。

        末尾に1つだけ Infinity を足してあり、これが「kana_dist に無いユニット」用の
        予備idに対応する(_ld が未知ユニットで Infinity を返すのと同じ)。

        kana_dist に unit が無い場合と、kana_dist が非対称(行のキーが全体の
        キー集合と一致しない)場合は None を返し、呼び出し側を _ld の経路に落とす。
        """
        values = self._row_values.get(unit, _MISSING)
        if values is _MISSING:
            row = self.kana_dist.get(unit)
            try:
                values = None if row is None else [row[u] for u in self._unit_ids] + [INF]
            except KeyError:
                values = None
            self._row_values[unit] = values
        return values  # type: ignore[return-value]

    def id_order(self, bucket_keys: tuple[str, ...], ids: Any) -> list[str]:
        """走査したバケツの並びに対する「単語idの JS オブジェクト列挙順」を返す。

        get_similar_word は結果を ``js_object_key_order(words.keys())`` の順に
        並べてから sim で安定ソートする。words の挿入順は「どのバケツをどの順に
        走査したか」だけで決まる(バケツ内の単語の並びも単語DB側で固定)ので、
        バケツの並びをキーにキャッシュすれば、同じ単語DBに対する2回目以降の
        呼び出しでは並べ直しを丸ごと省ける。
        """
        order = self._orders.get(bucket_keys)
        if order is None:
            order = js_object_key_order(list(ids))
            self._orders[bucket_keys] = order
        return order


def normalize_unit_weights(
    weights: Sequence[float] | None,
    unit_count: int,
    context: str = "",
) -> list[float] | None:
    """位置別重みを「平均1」に正規化する(w_i * n / sum(w))。

    平均1にそろえるのは、単語数ペナルティ(WORD_NUMBER_PENALTY)や文節境界の
    報酬/ペナルティのような「位置を持たない定数項」との相対スケールを保つため。
    正規化しないと、重みの絶対値を上げ下げしただけで一致距離と定数項の釣り合いが
    変わり、単語の切り方まで変わってしまう。

    不正な入力(長さ不一致・合計が0以下・負値・非有限値)は warning ログを出して
    None(=重みなし扱い)を返す。呼び出し側はその行を従来どおりに処理する。
    """
    if weights is None:
        return None
    where = f" ({context})" if context else ""
    if len(weights) != unit_count:
        logger.warning(
            "unit weights length mismatch%s: got %d, expected %d; ignoring weights",
            where,
            len(weights),
            unit_count,
        )
        return None
    if unit_count == 0:
        return None
    for w in weights:
        if not isinstance(w, (int, float)) or isinstance(w, bool) or not math.isfinite(w) or w < 0:
            logger.warning("invalid unit weight%s: %r; ignoring weights", where, w)
            return None
    total = float(sum(weights))
    if total <= 0:
        logger.warning("unit weights sum to %r%s; ignoring weights", total, where)
        return None
    return [float(w) * unit_count / total for w in weights]


class SoramimiMaker:
    """soramimic.js の SoramimiMaker(kanaSimilarity, textAnalyzer)。"""

    # JS側が maker.FILLER_COST を公開しているのに合わせる(テスト・呼び出し側の検証用)
    FILLER_COST = FILLER_COST

    def __init__(self, kana_similarity: KanaSimilarity, text_analyzer: TextAnalyzer) -> None:
        self.kana_similarity = kana_similarity
        self.text_analyzer = text_analyzer

    @staticmethod
    def _assign_default_parameter(parameters: dict[str, Any] | None) -> dict[str, Any]:
        default_parameter_values: dict[str, Any] = {
            "REPEAT": "100",
            "SPLITTER": "/",
            "DUPLICATE": True,
            "SAME_PHRASE_BREAK_REWARD": 1,
            "MID_PHRASE_BREAK_PENALTY": 0,  # 文節の途中で単語が切れることへのペナルティ(0で従来と同一) #98
            "WORD_NUMBER_PENALTY": 1,
            "VARIATION_COST": 0,  # ン/ッ/ーの1変換操作あたりのコスト(0で無効。#105)
            "LENGTH": 1,
        }
        if parameters:
            default_parameter_values.update(parameters)
        return default_parameter_values

    @staticmethod
    def _ld(
        s: list[str],
        t: list[str],
        kana_dist: SimTable,
        weights: Sequence[float] | None = None,
    ) -> float:
        """文字列(単位リスト)s と t の置換コストを求める(soramimic.js の ld)。

        長さ不一致・空・未知文字は Infinity を返す(JSの Inifinity タイポ経路含む)。

        weights: ターゲット(元歌詞)側 s のユニット位置ごとの重み(平均1に正規化済み)。
        None なら従来と完全に同一(ビット一致)。指定時は各ユニットの一致距離のみに
        掛ける。VARIATION_COST や WORD_NUMBER_PENALTY・文節境界項は無重みのままで、
        重み付けの対象を広げるかは将来の拡張。
        """
        if not s or not t:
            return INF
        if len(s) != len(t):
            return INF
        score = 0.0
        if weights is None:
            for i in range(len(s)):
                if s[i] in kana_dist and t[i] in kana_dist:
                    score += kana_dist[s[i]][t[i]]
                else:
                    return INF
            return score
        for i in range(len(s)):
            if s[i] in kana_dist and t[i] in kana_dist:
                score += kana_dist[s[i]][t[i]] * weights[i]
            else:
                return INF
        return score

    @staticmethod
    def _expand_weights(
        variation: list[str], unit_weights: Sequence[float] | None
    ) -> list[float] | None:
        """音節単位の重みを、変種展開後のユニット単位の重みに写す。

        変種は音節数とユニット数が一致しない(アン→["ア","ン"] / ["アー"] 等)。
        Variation.src が各出力ユニットの元音節indexを持つので、それで引き直す。
        src が無い/壊れている場合は重みなし扱い(従来動作)にフォールバックする。
        """
        if unit_weights is None:
            return None
        src = getattr(variation, "src", None)
        if not src or len(src) != len(variation):
            logger.warning("variation without usable src; ignoring unit weights for this candidate")
            return None
        if any(k < 0 or k >= len(unit_weights) for k in src):
            logger.warning("variation src out of range; ignoring unit weights for this candidate")
            return None
        return [unit_weights[k] for k in src]

    def get_similar_word(
        self,
        wordlist: dict[int, list[Word]],
        target: list[str],
        kana_dist: SimTable,
        length: int = 1,
        variation_cost: float = 0,
        unit_weights: Sequence[float] | None = None,
    ) -> list[Word]:
        """kanaDist下で target に距離の近い単語を求める(getSimilarWord)。

        variation_cost: ン/ッ/ーの1変換操作あたりに加算するコスト(#105)。
        unit_weights: target(音節単位)の位置別重み。平均1に正規化済みのものを
            渡すこと(normalize_unit_weights)。None なら従来と完全に同一。
        """
        return self._get_similar_word(
            _WordlistIndex(wordlist, kana_dist),
            target,
            kana_dist,
            variation_cost,
            unit_weights,
        )

    def _get_similar_word(
        self,
        index: _WordlistIndex,
        target: list[str],
        kana_dist: SimTable,
        variation_cost: float = 0,
        unit_weights: Sequence[float] | None = None,
    ) -> list[Word]:
        """get_similar_word の本体(前処理済みの単語DBインデックスを受け取る版)。

        出力は素朴な実装(単語ごとに _ld を呼ぶ)とビット単位で同一。速度のために
        変えたのは「回す順番」だけで、浮動小数の演算順序は変えていない:

          * 距離の合計は _ld と同じくユニット位置 0..L-1 の順に足し込む。
            単語ごとに足すか、位置ごとに全単語へ足すかは結果を変えない。
          * 候補(変種)は元と同じ順に見て ``d < sim`` のときだけ更新するので、
            同点なら先に出てきた候補が残るという性質もそのまま。
          * kana_dist に無いユニットを含む候補は全単語 Infinity になり
            ``min(Infinity, sim)`` は sim なので、丸ごと読み飛ばしてよい。
        """
        wordlist = index.wordlist
        tmp = self.text_analyzer.syllable_to_variation(target)
        candidates: dict[int, list[list[str]]] = {}
        # 変種ごとの展開済み重み(単語ループの内側で毎回引き直さないよう先に作る)
        candidate_weights: dict[int, list[list[float] | None]] = {}
        for c in tmp:
            clen = len(c)
            if clen not in wordlist:
                continue
            if clen not in candidates:
                candidates[clen] = []
                candidate_weights[clen] = []
            candidates[clen].append(c)
            candidate_weights[clen].append(self._expand_weights(c, unit_weights))

        # 単語idごとの「最良のsim」と「そのときの単語」。素朴版は毎回 {**w, "sim": sim} を
        # 作ってから捨てていたが、勝ち残った単語ぶんだけ最後に作れば結果は同じで、
        # 生成する dict の数(= 割り当てとGCの負荷)がバケツをまたぐ重複ぶん減る。
        best_sim: dict[str, float] = {}
        best_word: dict[str, Word] = {}
        bucket_keys = tuple(js_object_key_order([str(k) for k in candidates.keys()]))
        for i in bucket_keys:
            key = int(i)
            prons, vcosts, icols = index.bucket(key)
            n = len(prons)
            sims: list[float] | None = None

            for c, cwts in zip(candidates[key], candidate_weights[key], strict=True):
                # ターゲット側変種のコストは単語ループに依存しないのでここで1度だけ引く
                cvcost = getattr(c, "vcost", 0) or 0

                totals: list[float] | None = None
                if icols is not None:
                    rvs: list[list[float]] = []
                    for u in c:
                        rv = index.row_values(u)
                        if rv is None:
                            break
                        rvs.append(rv)
                    if len(rvs) == len(c):
                        if cwts is not None:
                            # 重みは各ユニットの距離に掛かるので、行ベクトル側に先に掛けておく
                            # (kana_dist[c[i]][u] * weights[i] と同じ演算・同じ丸め)
                            scaled = []
                            for rv, wt in zip(rvs, cwts, strict=True):
                                sv = [v * wt for v in rv]
                                # 未知ユニット枠は重みを掛けない(_ld も掛ける前に
                                # Infinity を返す。重み0だと Infinity*0=nan になる)
                                sv[-1] = INF
                                scaled.append(sv)
                            rvs = scaled
                        totals = _column_sums(rvs, icols, n)
                    elif c[len(rvs)] not in kana_dist:
                        # ターゲット側に未知ユニット → 全単語 Infinity。min に影響しない
                        continue

                if totals is None:
                    # 素朴な経路: 長さ不一致・未知ユニットを含むDBや非対称な行列など
                    ld = self._ld
                    totals = [ld(c, p, kana_dist, cwts) for p in prons]

                # ldの生スコアに変種コスト(ターゲット側 c.vcost + 単語側 w.vcost)を
                # 加算した素の合計にする(#105)。旧正規化(÷変種長×音節数)は
                # 対角0の新行列(#102/#104)では希釈の副作用だけが残るため廃止。
                # 変種コストは位置を持たないので重み付けの対象外(将来の拡張)。
                if variation_cost:
                    cur = [
                        t + (cvcost + v) * variation_cost
                        for t, v in zip(totals, vcosts, strict=True)
                    ]
                else:
                    # ``+ 0`` は値を変えないので足す前の合計をそのまま使う
                    cur = totals

                if sims is None:
                    sims = cur
                else:
                    # min(d, sim) と同じく、同点なら先の候補を残す
                    sims = [d if d < s else s for d, s in zip(cur, sims, strict=True)]

            if sims is None:  # 全候補が未知ユニット持ち
                sims = [INF] * n

            for w, sim in zip(wordlist[key], sims, strict=True):
                wid = w["id"]
                prev = best_sim.get(wid)
                if prev is not None and sim > prev:
                    continue
                best_sim[wid] = sim  # 同点は後勝ち(素朴版の上書き条件 sim <= prev と同じ)
                best_word[wid] = w

        # 共有オブジェクトを直接書き換えるとDPの再帰中に別セグメントの
        # クエリがsimを上書きし、スコア計算が汚染される(#99)。コピーに載せる
        order = index.id_order(bucket_keys, best_sim.keys())
        words2 = [{**best_word[wid], "sim": best_sim[wid]} for wid in order]
        words2.sort(key=_SIM_KEY)
        return words2

    def _convert(
        self,
        tokens: list[Token],
        get_similar_word_func: Callable[[list[str], int, int], list[Word]],
        used_words: list[str],
        param: dict[str, Any],
        locks: list[Word] | None = None,
    ) -> list[Any]:
        # get_similar_word_func は (部分ターゲット, 開始index, 終了index) を受け取る。
        # 位置別重みを引くために区間を渡す必要があるため、JS原典の1引数から拡張した。
        is_duplicate = param["DUPLICATE"]
        same_phrase_break = param["SAME_PHRASE_BREAK_REWARD"]
        # 未指定(旧呼び出し元)は0=従来と同一 #98
        mid_phrase_break = param.get("MID_PHRASE_BREAK_PENALTY") or 0
        words_num = param["WORD_NUMBER_PENALTY"]

        # 固定単語は使用済み扱い(可変リスト)
        # fillerはidを持たないので使用済みには含めない(固定されたfillerが来ても同じ)
        if locks and len(locks) > 0:
            used = list(used_words) + [v["id"] for v in locks if not v.get("filler")]
        else:
            used = used_words

        target = [v["pronunciation"] for v in tokens]
        phrase_breaks: list[int] = []
        for j, v in enumerate(tokens):
            if j == 0:
                phrase_breaks.append(0)
            elif v["phrase"] != tokens[j - 1]["phrase"]:
                phrase_breaks.append(j)

        memo: dict[tuple[int, int], list[Any]] = {}
        memo[(0, 0)] = [0, []]

        def dp(s: int, t: int) -> list[Any]:
            if (s, t) in memo:
                return memo[(s, t)]
            if s == t:
                memo[(s, t)] = [0, []]
                return memo[(s, t)]

            results: list[list[Any]] = []
            for i in range(s, t):
                subtarget = target[i:t]

                r = dp(s, i)
                if not r:
                    continue
                prev_score = r[0]
                if prev_score == INF:
                    continue
                prev_words = r[1]

                # 1ユニット区間には必ず filler(万能候補)を選択肢として置く(#128)。
                # コストが巨大なので実単語が置ける区間では必ず負け、単語が尽きた/
                # どの単語も合わない区間だけ「元歌詞のまま」で残る。これで
                # 「候補が無い→行が丸ごと空」という経路が無くなる。
                # 文節の報酬・ペナルティは単語の切れ目に対する調整なので未変換の
                # fillerには掛けない(経路の優劣がfillerの個数だけで決まるようにする)
                if t - i == 1:
                    kana = subtarget[0]
                    filler_words = list(prev_words)
                    filler_words.append(
                        {
                            "surface": kana,
                            "pronunciation": kana,
                            "kana": kana,
                            "original": "",
                            "filler": True,
                            "sim": FILLER_COST,
                            "score": FILLER_COST,
                            "originalkana": kana,
                            "period": [i, t],
                        }
                    )
                    results.append([prev_score + FILLER_COST + words_num, filler_words])

                similar_words = get_similar_word_func(subtarget, i, t)
                if similar_words is None:
                    continue

                # fillerはidを持たない仮想語なので、使用済み(単語重複なし)の判定からは外す
                current_used = [v["id"] for v in prev_words if not v.get("filler")]

                new_word: Word | None
                if len(similar_words) == 0:
                    new_word = None
                elif is_duplicate:
                    new_word = dict(similar_words[0])
                else:
                    new_word = None
                    for w in similar_words:
                        if w["id"] not in used and w["id"] not in current_used:
                            new_word = dict(w)
                            break

                if not new_word:
                    continue

                new_word["originalkana"] = "".join(subtarget)
                new_word["score"] = new_word["sim"]
                if t in phrase_breaks:
                    new_word["score"] -= same_phrase_break * 1
                elif t != len(target):
                    # 文節の途中で単語が切れる(終端が文節境界にも行末にも一致しない)ペナルティ #98
                    new_word["score"] += mid_phrase_break
                new_word["period"] = [i, t]

                new_score = prev_score + new_word["score"] + words_num
                new_words = list(prev_words)
                new_words.append(new_word)
                results.append([new_score, new_words])

            if len(results) == 0:
                result = [INF, []]
                memo[(s, t)] = result
                return result
            result = find_min(results, lambda v: v[0])
            memo[(s, t)] = result
            return result

        if locks and len(locks) > 0:
            sorted_locks = sorted(locks, key=lambda w: w["period"][0])
            score: float = 0
            words: list[Word] = []
            cursor = 0

            def take_segment(s: int, t: int) -> None:
                nonlocal score, words
                r = dp(s, t)
                if r and r[0] != INF:
                    score += r[0]
                    words = words + r[1]
                    # 後続区間で同じ単語を再利用しないよう使用済みに追記
                    # (fillerはidを持たないので数えない)
                    for w in r[1]:
                        if not w.get("filler"):
                            used.append(w["id"])

            for lw in sorted_locks:
                ls, le = lw["period"]
                if cursor < ls:
                    take_segment(cursor, ls)
                words.append(lw)
                cursor = max(cursor, le)
            if cursor < len(target):
                take_segment(cursor, len(target))
            return [score, words]

        return dp(0, len(target))

    def get_candidates(
        self,
        wordlist: dict[int, list[Word]],
        target: list[str],
        parameter: dict[str, Any] | None,
        length: int = 30,
    ) -> list[Word]:
        param = self._assign_default_parameter(parameter)
        kana_dist = self.kana_similarity.get_kana_similarity(param)
        words = (
            self.get_similar_word(wordlist, target, kana_dist, length, param["VARIATION_COST"])
            or []
        )
        return [dict(w) for w in words[:length]]

    def generate(
        self,
        phrases: list[str],
        wordlist: dict[int, list[Word]],
        parameter: dict[str, Any] | None,
        update_func: Callable[..., Any] | None = None,
        end_func: Callable[..., Any] | None = None,
        weights_per_line: list[list[float]] | None = None,
    ) -> list[list[Word]]:
        tokens_list = self.text_analyzer.tokenize_together(phrases)
        return self.generate_from_tokens(
            tokens_list,
            wordlist,
            parameter,
            update_func,
            end_func,
            weights_per_line=weights_per_line,
        )

    def generate_from_tokens(
        self,
        tokens_list: list[list[Token]],
        wordlist: dict[int, list[Word]],
        parameter: dict[str, Any] | None,
        update_func: Callable[..., Any] | None = None,
        end_func: Callable[..., Any] | None = None,
        locks_per_line: list[list[Word]] | None = None,
        weights_per_line: list[list[float]] | None = None,
    ) -> list[list[Word]]:
        """行ごとに近い単語列を割り当てる。

        weights_per_line: 行ごとの「音節ユニット位置別の重み」。各行の長さは
            その行の音節ユニット数(get_yomi_and_phrase_break 後のトークン数)と
            同じ非負floatの列。長い音符の音を優先して合わせる、といった用途向け。
            None(省略)なら従来と完全に同一の動作をする。重みは行ごとに平均1へ
            正規化され(normalize_unit_weights)、ターゲット側ユニットの一致距離
            だけに掛かる。VARIATION_COST・WORD_NUMBER_PENALTY・文節境界項は
            無重みのまま(重み付けの対象を広げるかは将来の拡張)。
        """
        param = self._assign_default_parameter(parameter)

        kana_dist = self.kana_similarity.get_kana_similarity(param)
        # 単語DBの前処理は行・区間をまたいで使い回す(kana_dist はこの generate 中不変)
        index = _WordlistIndex(wordlist, kana_dist)
        gsmemo: dict[str, list[Word]] = {}

        def make_gs(
            line_weights: list[float] | None,
        ) -> Callable[[list[str], int, int], list[Word]]:
            def gs(target: list[str], start: int, end: int) -> list[Word]:
                seg_weights = line_weights[start:end] if line_weights is not None else None
                joined_target = "".join(target)
                if seg_weights is None:
                    key = joined_target
                else:
                    # 位置別重みがあると同じカナ列でもスコアが変わるので、キャッシュを
                    # 汚さないようキーに重みベクトルを含める。区間(start,end)を含める
                    # 方式と違い、同じ重みパターンが繰り返す行ではキャッシュが効く。
                    # (重みが全行で相異なる場合はヒット率が落ちるが、正しさを優先する)
                    key = joined_target + "\x00" + ",".join(repr(w) for w in seg_weights)
                if key in gsmemo:
                    return gsmemo[key]
                result = self._get_similar_word(
                    index, target, kana_dist, param["VARIATION_COST"], seg_weights
                )
                gsmemo[key] = result
                return result

            return gs

        tokenized_phrases = [self.text_analyzer.get_yomi_and_phrase_break(v) for v in tokens_list]

        if weights_per_line is not None and len(weights_per_line) != len(tokenized_phrases):
            logger.warning(
                "weights_per_line length mismatch: got %d, expected %d lines",
                len(weights_per_line),
                len(tokenized_phrases),
            )

        used_words: list[str] = []
        results: list[list[Word]] = []

        for i in range(len(tokenized_phrases)):
            tokens = tokenized_phrases[i]
            raw_weights = (
                weights_per_line[i]
                if weights_per_line is not None and i < len(weights_per_line)
                else None
            )
            line_weights = normalize_unit_weights(raw_weights, len(tokens), context=f"line {i}")
            raw_result = self._convert(
                tokens,
                make_gs(line_weights),
                used_words,
                param,
                locks_per_line[i] if locks_per_line else None,
            )

            result: list[Word] = []
            if raw_result:
                for v in raw_result[1]:
                    original_surface = "".join(
                        tok["surface_form"] for tok in tokens[v["period"][0] : v["period"][1]]
                    )
                    v["original_surface"] = original_surface
                    result.append(v)

            if update_func:
                update_func(result, i, tokenized_phrases)
            # fillerは実単語ではないので使用済み(単語重複なし)には数えない
            used_words = used_words + [v["id"] for v in result if not v.get("filler")]
            results.append(result)

        if end_func:
            end_func(results)
        return results
