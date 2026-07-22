# 移植元: frontend/src/lib/soramimic.js
"""soramimic.js からの移植(ロジック無改変)。

SoramimiMaker: 発音の類似度に基づく DP で、各行の入力読みに近い単語列を割り当てる。
JSの setTimeout 連鎖は同期 for ループに置き換え、戻り値は results(行ごとの単語リストの
リスト)を返す(意図的な API 改善)。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .kana_similarity import KanaSimilarity, SimTable
from .text_analyzer import TextAnalyzer
from .utils import find_min, js_object_key_order

Token = dict[str, Any]
Word = dict[str, Any]

INF = float("inf")


class SoramimiMaker:
    """soramimic.js の SoramimiMaker(kanaSimilarity, textAnalyzer)。"""

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
    def _ld(s: list[str], t: list[str], kana_dist: SimTable) -> float:
        """文字列(単位リスト)s と t の置換コストを求める(soramimic.js の ld)。

        長さ不一致・空・未知文字は Infinity を返す(JSの Inifinity タイポ経路含む)。
        """
        if not s or not t:
            return INF
        if len(s) != len(t):
            return INF
        score = 0.0
        for i in range(len(s)):
            if s[i] in kana_dist and t[i] in kana_dist:
                score += kana_dist[s[i]][t[i]]
            else:
                return INF
        return score

    def get_similar_word(
        self,
        wordlist: dict[int, list[Word]],
        target: list[str],
        kana_dist: SimTable,
        length: int = 1,
        variation_cost: float = 0,
    ) -> list[Word]:
        """kanaDist下で target に距離の近い単語を求める(getSimilarWord)。

        variation_cost: ン/ッ/ーの1変換操作あたりに加算するコスト(#105)。
        """
        tmp = self.text_analyzer.syllable_to_variation(target)
        candidates: dict[int, list[list[str]]] = {}
        for c in tmp:
            clen = len(c)
            if clen not in wordlist:
                continue
            if clen not in candidates:
                candidates[clen] = []
            candidates[clen].append(c)

        words: dict[str, Word] = {}
        for i in js_object_key_order([str(k) for k in candidates.keys()]):
            key = int(i)
            for w in wordlist[key]:
                # 共有オブジェクトを直接書き換えるとDPの再帰中に別セグメントの
                # クエリがsimを上書きし、スコア計算が汚染される(#99)。コピーに載せる
                sim = INF
                for c in candidates[key]:
                    # ldの生スコアに変種コスト(ターゲット側 c.vcost + 単語側 w.vcost)を
                    # 加算した素の合計にする(#105)。旧正規化(÷変種長×音節数)は
                    # 対角0の新行列(#102/#104)では希釈の副作用だけが残るため廃止。
                    d = (
                        self._ld(c, w["pronunciation"], kana_dist)
                        + ((getattr(c, "vcost", 0) or 0) + (w.get("vcost") or 0)) * variation_cost
                    )
                    sim = min(d, sim)
                wid = w["id"]
                if wid in words and sim > words[wid]["sim"]:
                    continue
                words[wid] = {**w, "sim": sim}

        words2 = [words[wid] for wid in js_object_key_order(list(words.keys()))]
        words2.sort(key=lambda a: a["sim"])
        return words2

    def _convert(
        self,
        tokens: list[Token],
        get_similar_word_func: Callable[[list[str]], list[Word]],
        used_words: list[str],
        param: dict[str, Any],
        locks: list[Word] | None = None,
    ) -> list[Any]:
        is_duplicate = param["DUPLICATE"]
        same_phrase_break = param["SAME_PHRASE_BREAK_REWARD"]
        # 未指定(旧呼び出し元)は0=従来と同一 #98
        mid_phrase_break = param.get("MID_PHRASE_BREAK_PENALTY") or 0
        words_num = param["WORD_NUMBER_PENALTY"]

        # 固定単語は使用済み扱い(可変リスト)
        if locks and len(locks) > 0:
            used = list(used_words) + [v["id"] for v in locks]
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
                similar_words = get_similar_word_func(subtarget)
                if similar_words is None:
                    continue

                r = dp(s, i)
                if not r:
                    continue
                prev_score = r[0]
                if prev_score == INF:
                    continue
                prev_words = r[1]
                current_used = [v["id"] for v in prev_words]

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
                    for w in r[1]:
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
    ) -> list[list[Word]]:
        tokens_list = self.text_analyzer.tokenize_together(phrases)
        return self.generate_from_tokens(tokens_list, wordlist, parameter, update_func, end_func)

    def generate_from_tokens(
        self,
        tokens_list: list[list[Token]],
        wordlist: dict[int, list[Word]],
        parameter: dict[str, Any] | None,
        update_func: Callable[..., Any] | None = None,
        end_func: Callable[..., Any] | None = None,
        locks_per_line: list[list[Word]] | None = None,
    ) -> list[list[Word]]:
        param = self._assign_default_parameter(parameter)

        kana_dist = self.kana_similarity.get_kana_similarity(param)
        gsmemo: dict[str, list[Word]] = {}

        def gs(target: list[str]) -> list[Word]:
            joined_target = "".join(target)
            if joined_target in gsmemo:
                return gsmemo[joined_target]
            result = self.get_similar_word(
                wordlist, target, kana_dist, 100, param["VARIATION_COST"]
            )
            gsmemo[joined_target] = result
            return result

        tokenized_phrases = [self.text_analyzer.get_yomi_and_phrase_break(v) for v in tokens_list]

        used_words: list[str] = []
        results: list[list[Word]] = []

        for i in range(len(tokenized_phrases)):
            tokens = tokenized_phrases[i]
            raw_result = self._convert(
                tokens,
                gs,
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
            used_words = used_words + [v["id"] for v in result]
            results.append(result)

        if end_func:
            end_func(results)
        return results
