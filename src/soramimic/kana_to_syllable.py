# 移植元: frontend/src/lib/kanaToSyllable.js
"""kanaToSyllable.js からの移植(ロジック無改変)。

カナ文字列をモウラ/シラブル単位に分割し、発音バリエーションを生成する。
"""

from __future__ import annotations

import re
from typing import Any


def _match_all(pattern: re.Pattern[str], text: str) -> list[str] | None:
    """JSの ``String.match(/.../g)`` 相当。マッチが無ければ None を返す。"""
    matches = [m.group(0) for m in pattern.finditer(text)]
    return matches if matches else None


class Variation(list[str]):
    """ユニット列(list[str])に変種コスト vcost を持たせたリスト(#105)。

    JSでは配列に ``.vcost`` プロパティを直接生やしている。list のサブクラスなので
    既存の list[str] を期待するコードとそのまま互換。

    ``src`` は各出力ユニットが由来する入力音節のindex列(長さは self と同じ)。
    ン→ー化や促音削除でユニット数が変わっても、位置別の重み(ユニット位置別
    スコアリング)を元音節の位置に対応づけられるようにするために持たせる。
    """

    vcost: int = 0
    # クラス既定は空リスト。get_variation は必ずインスタンス側で上書きするため
    # 共有されるのは「srcを持たない手書きVariation」だけで、読み取り専用に扱う。
    src: list[int] = []


def char_to_consonant(char: str) -> str:
    """文字を子音記号に変換(kanaToSyllable.js の charToConsonant)。

    JSのオブジェクトリテラルで ``sp`` キーが二度定義され、後者(``ンッ``)で上書き
    される。そのため ``アイウエオヲー`` はどの子音にもマッチせず "" を返す。
    """
    cols = {
        "sp": "アイウエオヲー",
        "k": "カキクケコ",
        "s": "サシスセソ",
        "t": "タチツテト",
        "n": "ナニヌネノ",
        "h": "ハヒフヘホ",
        "m": "マミムメモ",
        "y": "ヤユヨ",
        "r": "ラリルレロ",
        "w": "ワ",
        "g": "ガギグゲゴ",
        "z": "ザジヂズゼゾ",
        "d": "ダヅデド",
        "b": "バビブヴベボ",
        "p": "パピプペポ",
        "sp": "ンッ",  # noqa: F601  上のspを上書き(JS挙動を忠実に再現)
    }
    first = char[0]
    consonant = ""
    for c, col in cols.items():
        if first in col:
            consonant = c
            break
    return consonant


def char_to_vowel(char: str) -> str:
    """文字を母音カナに変換(kanaToSyllable.js の charToVowel)。"""
    if char == "ー":
        return char

    # 伸ばし棒を除いた末尾の文字を取得
    last = char[len(char) - 1]
    for i in range(len(char) - 1, -1, -1):
        last = char[i]
        if last != "ー":
            break

    rows: dict[str, Any] = {
        "ア": "アカサタナハマヤラワガザダバパァャヮ",
        "イ": "イキシチニヒミリギジヂビピィ",
        "ウ": "ウクスツヌフムユルグズヅブプヴゥュ",
        "エ": "エケセテネヘメレゲゼデベペェ",
        "オ": "オコソトノホモヨロゴゾドボポォ",
        "sp": ["sp", "ン", "ッ"],
    }
    vowel = last
    for v, row in rows.items():
        if last in row:
            vowel = v
            break
    return vowel


def bar_to_vowel(text: str) -> str:
    """伸ばし棒を母音カナへ展開(kanaToSyllable.js の barToVowel)。"""

    def _repl(match: re.Match[str]) -> str:
        m = match.group(0)
        first = m[0]
        vowel = char_to_vowel(first)
        if first == "ン":
            vowel = "ン"
        elif first == "ッ":
            vowel = "ッ"
        return first + vowel

    return re.sub(r"[ァ-ンヴ]ー", _repl, text)


def vowel_to_bar(text: str) -> None:
    """kanaToSyllable.js の vowelToBar を忠実に移植。

    JS版は replace 結果を return していないため戻り値は undefined。
    """

    def _repl(match: re.Match[str]) -> str:
        m = match.group(0)
        first = m[0]
        vowel = char_to_vowel(first)
        res = m
        if vowel == m[1]:
            res = first + "ー"
        elif vowel == "エ" and m[1] == "イ":
            res = first + "ー"
        elif vowel == "オ" and m[1] == "ウ":
            res = first + "ー"
        return res

    re.sub(r"[ァ-ンヴ][アイウエオ]", _repl, text)
    return None


# 同じ文字か判定
def is_same_kana(kana1: str, kana2: str) -> bool:
    return kana1 == kana2


# 同じ母音か判定
def is_same_vowel(kana1: str, kana2: str) -> bool:
    return char_to_vowel(kana1) == char_to_vowel(kana2)


# 同じ子音か判定
def is_same_consonant(kana1: str, kana2: str) -> bool:
    return char_to_consonant(kana1) == char_to_consonant(kana2)


# どちらも長音かどうか
def is_same_bar(kana1: str, kana2: str) -> bool:
    check_char = "ー"
    return kana1[-1:] == check_char and kana2[-1:] == check_char


# どちらも促音かどうか
def is_same_sokuon(kana1: str, kana2: str) -> bool:
    check_char = "ッ"
    return kana1[-1:] == check_char and kana2[-1:] == check_char


# どちらも撥音かどうか
def is_same_hatsuon(kana1: str, kana2: str) -> bool:
    check_char = "ン"
    return kana1[-1:] == check_char and kana2[-1:] == check_char


def hira_to_kata(s: str) -> str:
    """ひらがなをカタカナに変換(kanaToSyllable.js の hiraToKata)。"""

    def _repl(match: re.Match[str]) -> str:
        return chr(ord(match.group(0)) + 0x60)

    return re.sub(r"[ぁ-ゖ]", _repl, s)


def kana_pattern() -> dict[str, str]:
    """日本語カナの正規表現パターン集合(kanaToSyllable.js の KanaPattern)。"""
    kana_a = "[アカサタナハマヤラワガザダバパ]"
    kana_i = "[イキシチニヒミリギジヂビピ]"
    kana_i2 = kana_i.replace("イ", "")  # ャュョとくっつける用のイ段
    kana_u = "[ウクスツヌフムユルグズヅブプヴ]"
    kana_e = "[エケセテネヘメレゲゼデベペ]"
    kana_o = "[オコソトノホモヨロヲゴゾドボポ]"
    kana_td = "[テデ]"

    kana_multi_a = "(" + "|".join([kana_u + "[ァヮ]", kana_i2 + "ャ", kana_td + "ャ"]) + ")"
    kana_multi_i = "(" + "|".join([kana_u + "ィ", kana_td + "ィ"]) + ")"
    kana_multi_u = "(" + "|".join([kana_i + "ュ", kana_td + "ュ", "[トド]ゥ"]) + ")"
    kana_multi_e = "(" + "|".join([kana_u + "ェ", kana_i + "ェ"]) + ")"
    kana_multi_o = "(" + "|".join([kana_u + "ォ", kana_i2 + "ョ"]) + ")"
    kana_multi = (
        "("
        + "|".join(
            [
                kana_u + "[ァィェォ]",
                kana_td + "[ャィュョ]",
                kana_i + "[ャュョ]",
                kana_i2 + "ェ",
                "[トド]ゥ",
            ]
        )
        + ")"
    )

    kana_single_base = "[アイウエオ-ヂツ-モヤユヨ-ロワヲヴ]"
    kana_base = "(" + "|".join([kana_multi, kana_single_base]) + ")"
    kana_all = "(" + "|".join([kana_multi, "[ァ-ヴー]"]) + ")"

    return {
        "base": kana_base,
        "all": kana_all,
        "multi_a": kana_multi_a,
        "multi_i": kana_multi_i,
        "multi_u": kana_multi_u,
        "multi_e": kana_multi_e,
        "multi_o": kana_multi_o,
        "multi": kana_multi,
        "single_a": kana_a,
        "single_i": kana_i,
        "single_u": kana_u,
        "single_e": kana_e,
        "single_o": kana_o,
        "single_td": kana_td,
        "single_base": kana_single_base,
    }


def small_vowel_to_bar(text: str) -> str:
    """小文字母音を長音に変換(kanaToSyllable.js の smallVowelToBar)。"""
    replaced_text = re.sub(r"ー(ァ+|ィ+|ゥ+|ェ+|ォ+)", "ー", text)

    def _repl(match: re.Match[str]) -> str:
        m = match.group(0)
        res = m
        l2s = {"ア": "ァ", "イ": "ィ", "ウ": "ゥ", "エ": "ェ", "オ": "ォ"}
        first_vowel = char_to_vowel(m[0])
        if first_vowel in l2s and l2s[first_vowel] == m[1]:
            res = m[0] + "ー"
        elif len(m) >= 3:
            res = m[0] + m[1] + "ー"
        return res

    replaced_text = re.sub(r"[ァ-ヴ](ァ+|ィ+|ゥ+|ェ+|ォ+)", _repl, replaced_text)
    return replaced_text


def small_vowel_to_large(text: str) -> str:
    """2文字カナの一部でない小文字(ッを除く)を大文字にする(smallVowelToLarge)。"""
    s2l = {
        "ァ": "ア",
        "ィ": "イ",
        "ゥ": "ウ",
        "ェ": "エ",
        "ォ": "オ",
        "ヮ": "ワ",
        "ャ": "ヤ",
        "ュ": "ユ",
        "ョ": "ヨ",
    }

    def _repl(match: re.Match[str]) -> str:
        m = match.group(0)
        if re.search(r"[ウクスツヌフムユルグズヅブプヴ][ァヮォ]", m):
            return m
        elif re.search(r"[トド]ゥ", m):
            return m
        elif re.search(r"[キシチニヒミリギジヂビピテデ][ャュョ]", m):
            return m
        elif re.search(r"[ウクスツヌフムユルグズヅブプヴテデ]ィ", m):
            return m
        elif re.search(r"[ウクスツヌフムユルグズヅブプヴイキシチニヒミリギジヂビピ]ェ", m):
            return m
        else:
            return re.sub(r"[ァィゥェォヮャュョ]", lambda mm: s2l[mm.group(0)], m, count=1)

    replaced_text = re.sub(r".[ァィゥェォヮャュョ]", _repl, text)
    # 先頭の置換(JSは /gm。行頭ごとに置換)
    replaced_text = re.sub(
        r"^[ァィゥェォヮャュョ]", lambda mm: s2l[mm.group(0)], replaced_text, flags=re.MULTILINE
    )
    return replaced_text


#: 小書きカナ→大文字カナの対応(ひらがな・カタカナ両方)
_SMALL_TO_LARGE_KANA = {
    "ァ": "ア",
    "ィ": "イ",
    "ゥ": "ウ",
    "ェ": "エ",
    "ォ": "オ",
    "ヮ": "ワ",
    "ャ": "ヤ",
    "ュ": "ユ",
    "ョ": "ヨ",
    "ぁ": "あ",
    "ぃ": "い",
    "ぅ": "う",
    "ぇ": "え",
    "ぉ": "お",
    "ゎ": "わ",
    "ゃ": "や",
    "ゅ": "ゆ",
    "ょ": "よ",
}
#: 直前のカナと組み合わせて1モーラを構成する小書きカナの並び(カタカナ正規化後で判定)。
#: KanaToSyllable().split が1ユニットとして切り出す組み合わせ(kana_pattern の multi)と
#: 同じ集合にしておくこと。ここで残した並びが split で分かれると単独の小書きが残る
_STICKY_SMALL_KANA_RE = re.compile(
    r"^(?:[ウクスツヌフムユルグズヅブプヴ][ァィェォ]"  # ファ・ウィ・フェ・フォ など
    r"|[テデ][ャィュョ]"  # ティ・ディ・テュ など
    r"|[イキシチニヒミリギジヂビピ][ャュョ]"  # 拗音(キャ・シュ・ニョ など)
    r"|[キシチニヒミリギジヂビピ]ェ"  # シェ・チェ・ジェ など
    r"|[トド]ゥ)$"  # トゥ・ドゥ
)


def absorb_small_kana(text: str) -> str:
    """直前のカナと組み合わせて1モーラにならない小書きカナを大文字に直す。

    「ハァ」「ウッセェ」「リィ」のような引き伸ばし表記や、単独で現れた小書きが対象。
    置換は必ず1文字→1文字で文字列長を変えないので、読みと表層の位置対応
    (char_index / mora)を使う呼び出し元を壊さない。促音ッ・長音ーには触らない。

    本体JS(kanaToSyllable.js の absorbSmallKana)と同じ挙動。
    """
    if not text:
        return text
    chars: list[str] = []
    for i, c in enumerate(text):
        large = _SMALL_TO_LARGE_KANA.get(c)
        if large is None:
            chars.append(c)
            continue
        # 直前の文字は正規化後のものを見る(「スゥィ」→「スウィ」のように、
        # 大文字化した結果くっつけられるようになる並びを拾うため)
        prev = hira_to_kata(chars[i - 1]) if i > 0 else ""
        sticky = bool(_STICKY_SMALL_KANA_RE.match(prev + hira_to_kata(c)))
        chars.append(c if sticky else large)
    return "".join(chars)


def remove_bar_and_sokuon_reputation(text: str) -> str:
    """ーとッの不自然な並びを削除する(removeBarAndSokuonReputation)。"""
    text = re.sub(r"ー+", "ー", text)  # ーの連続を1文字にする
    text = re.sub(r"ッ[ーッ]+", "ッ", text)  # ッの後ろのーまたはッの連続を削除
    text = re.sub(r"^[ーッ]+", "", text)  # 先頭の[ーッ]を削除
    return text


def remove_unnatural_kana_pattern(text: str) -> str:
    """小文字や長音、促音の不自然な並びを解消する(removeUnnaturalKanaPattern)。"""
    text = small_vowel_to_bar(text)
    text = small_vowel_to_large(text)
    text = remove_bar_and_sokuon_reputation(text)
    return text


_MORA_RE = re.compile(
    r"[ウクスツヌフムユルグズヅブプ][ァヮィェォ]|[キシチニヒミリギジヂビピテデ][ャュョ]"
    r"|[イキシチニヒミリギジヂビピ]ェ|[テデ]ィ|[トド]ゥ|[ァ-ヴー]"
)


def mora_split(text: str) -> list[str] | None:
    """入力カナをモウラ単位で分かち書きする(moraSplit)。"""
    return _match_all(_MORA_RE, text)


class KanaToMora:
    def __init__(self) -> None:
        self._re = _MORA_RE

    def split(self, text: str) -> list[str] | None:
        return _match_all(self._re, text)


#: 1音節ぶんの変種。(空文字を除いたユニット列, 操作数c)。
SyllableVariant = tuple[tuple[str, ...], int]

#: 音節文字列 → 変種列 のキャッシュ。音節の種類はカナの組み合わせ上せいぜい数千で、
#: 単語リスト1本の中で同じ音節が何万回も現れるため、正規表現判定を使い回す。
_SYLLABLE_VARIATION_CACHE: dict[str, tuple[SyllableVariant, ...]] = {}

_RE_BARE_VOWEL = re.compile(r"^[アイウエオ]$")
_RE_BARE_NQ = re.compile(r"^[ンッ]$")
_RE_ENDS_VOWEL = re.compile(r"[アイウエオ]$")


def syllable_variations(syllable: str) -> tuple[SyllableVariant, ...]:
    """1音節の発音バリエーションを (ユニット列, 操作数) の列で返す。

    kanaToSyllable.js の getVariation 内の分岐そのもの。JS版が最後に
    ``flatMap(o=>o.u).filter(v=>v!=="")`` で落とす空ユニットは、どの分岐でも
    「空だけの変種」としてしか現れないので、ここで先に除いておく(結果は同じ)。
    """
    cached = _SYLLABLE_VARIATION_CACHE.get(syllable)
    if cached is not None:
        return cached

    variation: list[tuple[list[str], int]]
    if _RE_BARE_VOWEL.match(syllable):  # アイウエオは先に処理
        variation = [([syllable], 0)]
    elif _RE_BARE_NQ.match(syllable):
        variation = [([syllable], 0), ([""], 1)]  # 裸ン・ッの削除
    elif syllable == "ンー":  # ンー→["ン","ン"],["ン"],[""]
        variation = [
            (["ン", "ン"], 1),  # ー→ン変換
            (["ン"], 1),  # ー削除
            ([""], 2),  # ン削除+ー削除
        ]
    elif syllable == "ンッ":  # ンッ→["ン","ッ"],["ン"],["ッ"],[""]
        variation = [
            (["ン", "ッ"], 0),
            (["ン"], 1),  # ッ削除
            (["ッ"], 1),  # ン削除
            ([""], 2),
        ]
    elif syllable.endswith("ーン"):  # ex: アーン→["アー","ン"],["アー"]
        head = syllable[:-2]
        variation = [([head + "ー", "ン"], 0), ([head + "ー"], 1)]  # ン削除
    elif syllable.endswith("ンッ"):  # ex: アンッ→[...]
        head = syllable[:-2]
        variation = [
            ([head, "ン", "ッ"], 0),
            ([head, "ン"], 1),  # ッ削除
            ([head + "ー", "ッ"], 1),  # ン→ー化
            ([head + "ー"], 2),  # ン→ー化+ッ削除
            ([head, "ッ"], 1),  # ン削除
        ]
    elif syllable.endswith("ーッ"):  # ex. アーッ→["アー","ッ"],["アー"]
        head = syllable[:-2]
        variation = [([head + "ー", "ッ"], 0), ([head + "ー"], 1)]  # ッ削除
    elif syllable.endswith("ー"):  # ex. アー→["アー"]
        variation = [([syllable[:-1] + "ー"], 0)]
    elif syllable.endswith("ッ"):  # ex. アッ→["ア","ッ"],["ア"],["アー"]
        head = syllable[:-1]
        variation = [
            ([head, "ッ"], 0),
            ([head], 1),  # ッ削除
            ([head + "ー"], 1),  # ッ→ー置換(単一操作でッ↔ーを閉じる)
        ]
    elif syllable.endswith("ン"):  # ex. アン→["ア","ン"],["アー"],["ア"]
        head = syllable[:-1]
        variation = [
            ([head, "ン"], 0),
            ([head + "ー"], 1),  # ン→ー化
            ([head], 1),  # ン削除(単一操作でン削除を閉じる)
        ]
    elif _RE_ENDS_VOWEL.search(syllable):  # カア→["カ","ア"],["カー"]
        head = syllable[:-1]
        vowel = syllable[len(syllable) - 1]
        variation = [
            ([head, vowel], 0),
            ([head + "ー"], 0),  # 表記ゆれ(母音連続→ー)扱いで無コスト
        ]
    else:  # 1モーラ
        variation = [([syllable], 0)]

    result = tuple((tuple(u for u in units if u != ""), cost) for units, cost in variation)
    _SYLLABLE_VARIATION_CACHE[syllable] = result
    return result


class KanaToSyllable:
    """kanaToSyllable.js の KanaToSyllable() 相当。"""

    def __init__(self) -> None:
        kana = kana_pattern()
        re2 = r"ーッ|ンッ|ーン(?![ーッ])"
        re1 = r"ー|ッ|ン(?!ー)"
        re_back = "(" + "|".join([re2, re1]) + ")"

        re_multi_bar = "(" + kana["multi"] + re_back + ")"

        re_multi_a = kana["multi_a"] + "ア"
        re_multi_i = kana["multi_i"] + "イ(?![ェ])"
        re_multi_u = kana["multi_u"] + "ウ(?![ァィェォ])"
        re_multi_e = kana["multi_e"] + "[エイ]"
        re_multi_o = kana["multi_o"] + "(オ|ウ(?![ァィェォ]))"
        re_multi_vowel = (
            "(" + "|".join([re_multi_a, re_multi_i, re_multi_u, re_multi_e, re_multi_o]) + ")"
        )
        re_multi_vowel += "(?![ーンッ])"

        re_multi_unit = kana["multi"]

        re_n_bar = r"ン([ーッ]|ーッ)"

        re_single_bar = "(" + kana["single_base"] + re_back + ")"

        re_single_a = kana["single_a"] + "ア"
        re_single_i = kana["single_i"] + "イ"
        re_single_u = kana["single_u"] + "ウ(?![ァィェォ])"
        re_single_e = kana["single_e"] + "[エイ]"
        re_single_o = kana["single_o"] + "(オ|ウ(?![ァィェォ]))"
        re_single_vowel = (
            "(" + "|".join([re_single_a, re_single_i, re_single_u, re_single_e, re_single_o]) + ")"
        )
        re_single_vowel += "(?![ーンッ])"

        re_single_unit = "[ァ-ヴー]"

        re_all = "|".join(
            [
                re_multi_bar,
                re_multi_vowel,
                re_multi_unit,
                re_n_bar,
                re_single_bar,
                re_single_vowel,
                re_single_unit,
            ]
        )
        self._re_all = re.compile(re_all)

        re_multi_kana_full = "|".join(
            [
                re_multi_bar,
                re_multi_vowel,
                re_multi_unit,
                re_n_bar,
                re_single_bar,
                re_single_vowel,
            ]
        )
        re_multi_kana_full = "^(" + re_multi_kana_full + ")$"
        self._re_multi_kana_full = re.compile(re_multi_kana_full)

    def is_fullmatch(self, text: str) -> bool:
        return self._re_multi_kana_full.search(text) is not None

    def split(self, text: str) -> list[str] | None:
        return _match_all(self._re_all, text)

    def get_variation(
        self, syllables: list[str] | None, max_units: int | None = None
    ) -> list[Variation]:
        """カナ発音のバリエーションを取得する(getVariation)。

        各変種に変換操作回数(コスト)を付与する(#105)。ン→ー化・ッ削除・
        裸ン/ッ削除・ー削除=各1操作、複合音節は合計、無変換や表記ゆれ
        (母音連続→ー)=0。返り値は従来同様のユニット配列(文字列配列)だが、
        各配列(Variation)に .vcost 属性で操作回数の合計を持たせる。

        また各 Variation に .src(出力ユニットごとの入力音節index)を持たせる。
        ユニット数が変わる変種(アン→アー等)でも位置別の重みを元の音節位置に
        対応づけられるようにするため。

        max_units: 生成する変種のユニット数の上限(既定 None = 無制限で JS と同一)。
            指定すると ``[v for v in get_variation(s) if len(v) <= max_units]`` と
            **完全に同じリスト**(順序・vcost・src 込み)を返す。違いは、超過する
            変種を作ってから捨てるのではなく直積を途中で枝刈りする点だけ。
            変種数は音節数に対して指数的に増える(ン・ッ・母音連続を含む音節が
            それぞれ2〜5通りに分岐する)ので、長い読みの単語では上限指定が効く。
            単語リスト側の変種は「ユニット数が完全一致する変種」としか照合されない
            (maker._ld は長さ不一致を Infinity にする)ため、生成対象の歌詞行の
            最大ユニット数を上限に渡せば結果は変わらない。
        """
        if not syllables:
            return []

        variants_list: list[tuple[SyllableVariant, ...]] = []
        src_index: list[int] = []  # variants_list[j] が由来する syllables のindex
        for syllable_index, syllable in enumerate(syllables):
            if syllable is None:
                continue
            variants_list.append(syllable_variations(syllable))
            src_index.append(syllable_index)
        if not variants_list:
            return []

        n = len(variants_list)
        # suffix_min[i] = i番目以降の音節が最低でも生むユニット数(枝刈りの下界)
        suffix_min = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            suffix_min[i] = suffix_min[i + 1] + min(len(units) for units, _ in variants_list[i])
        if max_units is not None and suffix_min[0] > max_units:
            return []

        # 音節ごとの「継ぎ足す断片」(ユニット列, 元音節index列, 操作数, ユニット数)。
        # 直積の内側ループから追い出すため、あらかじめリスト化しておく。
        chunks_per_level = [
            [(list(units), [src_index[i]] * len(units), cost, len(units)) for units, cost in level]
            for i, level in enumerate(variants_list)
        ]

        # 直積を深さ優先で辿り、作業バッファ units_buf / src_buf を伸ばし縮みさせながら
        # 葉でだけコピーする。utils.product のように全組み合わせを一度に持たないので、
        # 使うメモリは出力ぶんだけで済む。最後の音節を最も速く回すため並び順も product と同じ。
        # 読みが長いと再帰では深さ制限に当たるので明示スタックで回す。
        out: list[Variation] = []
        units_buf: list[str] = []
        src_buf: list[int] = []
        cursor = [0] * n  # cursor[i] = レベルiで次に試す断片のindex
        pushed = [0] * n  # pushed[i] = レベルiがいま積んでいるユニット数
        costs = [0] * (n + 1)  # costs[i] = レベルiに入った時点の操作数合計
        level = 0
        last = n - 1
        while level >= 0:
            if pushed[level]:  # 直前に積んだ断片を戻す
                del units_buf[len(units_buf) - pushed[level] :]
                del src_buf[len(src_buf) - pushed[level] :]
                pushed[level] = 0
            chunks = chunks_per_level[level]
            i = cursor[level]
            if i >= len(chunks):
                level -= 1
                continue
            cursor[level] = i + 1
            chunk_units, chunk_src, chunk_cost, chunk_len = chunks[i]
            if (
                max_units is not None
                and len(units_buf) + chunk_len + suffix_min[level + 1] > max_units
            ):
                continue
            units_buf.extend(chunk_units)
            src_buf.extend(chunk_src)
            pushed[level] = chunk_len
            cost = costs[level] + chunk_cost
            if level == last:
                if units_buf:  # JSの filter(v=>v!=="") の結果が空になる変種は捨てる
                    flat = Variation(units_buf)
                    flat.vcost = cost  # 操作回数の合計
                    flat.src = list(src_buf)
                    out.append(flat)
                continue
            costs[level + 1] = cost
            level += 1
            cursor[level] = 0
            pushed[level] = 0
        return out


def get_kana_to_vowel_dictionary(kana2phonon_dictionary: dict[str, Any]) -> dict[str, str]:
    """kanaToSyllable.js の getKanaToVowelDictionary。"""
    k2r = kana2phonon_dictionary
    roma2vowel: dict[str, str] = {}
    for v1, v2 in zip("aiueo", "アイウエオ", strict=False):
        roma2vowel[v1] = v2
    roma2vowel["p"] = "sp"
    roma2vowel["N"] = "sp"
    roma2vowel["q"] = "sp"

    prev: dict[str, str] = {}
    for kana in list(k2r.keys()):
        roma_vowel_of_kana = k2r[kana][1][-1]  # kanaのローマ字表記の最後の文字(=母音)
        prev[kana] = roma2vowel[roma_vowel_of_kana]
        if kana in "ンッ":
            pass
        elif kana == "sp":
            pass
        else:
            prev[kana + "ー"] = prev[kana]
            if prev[kana] == "エ":
                prev[kana + "イ"] = prev[kana]
            elif prev[kana] == "オ":
                prev[kana + "ウ"] = prev[kana]
    return prev


def phonon_split(text: str) -> list[str] | None:
    """phononの単位でsplitする(phononSplit)。

    JS原典は未定義の getKanaPattern を呼ぶため実行時エラーになる(デッドコード)。
    移植では KanaPattern を用いて意図した挙動を再現する。
    """
    kana = kana_pattern()

    re_multi_bar = "(" + kana["multi"] + "ー)"
    re_multi_a = kana["multi_a"] + "ア"
    re_multi_i = kana["multi_i"] + "イ(?![ェ])"
    re_multi_u = kana["multi_u"] + "ウ(?![ァィェォ])"
    re_multi_e = kana["multi_e"] + "[エイ]"
    re_multi_o = kana["multi_o"] + "(オ|ウ(?![ァィェォ]))"
    re_multi_vowel = (
        "(" + "|".join([re_multi_a, re_multi_i, re_multi_u, re_multi_e, re_multi_o]) + ")"
    )
    re_multi_vowel += "(?!ー)"
    re_multi_unit = kana["multi"]
    re_n_bar = "ンー"
    re_single_bar = "(" + kana["single_base"] + "ー)"
    re_single_a = kana["single_a"] + "ア"
    re_single_i = kana["single_i"] + "イ"
    re_single_u = kana["single_u"] + "ウ(?![ァィェォ])"
    re_single_e = kana["single_e"] + "[エイ]"
    re_single_o = kana["single_o"] + "(オ|ウ(?![ァィェォ]))"
    re_single_vowel = (
        "(" + "|".join([re_single_a, re_single_i, re_single_u, re_single_e, re_single_o]) + ")"
    )
    re_single_vowel += "(?!ー)"
    re_single_unit = "[ァ-ヴー]"
    re_pat = "|".join(
        [
            re_multi_bar,
            re_multi_vowel,
            re_multi_unit,
            re_n_bar,
            re_single_bar,
            re_single_vowel,
            re_single_unit,
        ]
    )
    return _match_all(re.compile(re_pat), text)


class KanaConverter:
    """kanaToSyllable.js の createKanaConverter が返すオブジェクト相当。

    実際に外部から使われるのは separate / get_pronunciation_variation と
    is_same_* のみ(KANA2VOWEL 等は JS でも返り値に含まれずデッドコード)。
    """

    def __init__(self, kana2phonon: dict[str, Any]) -> None:
        self._k2s = KanaToSyllable()
        self.kana2vowel = get_kana_to_vowel_dictionary(kana2phonon)

    def separate(self, text: str) -> list[str] | None:
        return self._k2s.split(text)

    def get_pronunciation_variation(
        self, syllables: list[str] | None, max_units: int | None = None
    ) -> list[Variation]:
        return self._k2s.get_variation(syllables, max_units)

    is_same_kana = staticmethod(is_same_kana)
    is_same_vowel = staticmethod(is_same_vowel)
    is_same_consonant = staticmethod(is_same_consonant)
    is_same_bar = staticmethod(is_same_bar)
    is_same_hatsuon = staticmethod(is_same_hatsuon)
    is_same_sokuon = staticmethod(is_same_sokuon)


def create_kana_converter(kana2phonon: dict[str, Any]) -> KanaConverter:
    return KanaConverter(kana2phonon)
