# 移植元: frontend/src/lib/kanaToSyllable.js
"""kanaToSyllable.js からの移植(ロジック無改変)。

カナ文字列をモウラ/シラブル単位に分割し、発音バリエーションを生成する。
"""

from __future__ import annotations

import re
from typing import Any

from .utils import product


def _match_all(pattern: re.Pattern[str], text: str) -> list[str] | None:
    """JSの ``String.match(/.../g)`` 相当。マッチが無ければ None を返す。"""
    matches = [m.group(0) for m in pattern.finditer(text)]
    return matches if matches else None


class Variation(list):
    """ユニット列(list[str])に変種コスト vcost を持たせたリスト(#105)。

    JSでは配列に ``.vcost`` プロパティを直接生やしている。list のサブクラスなので
    既存の list[str] を期待するコードとそのまま互換。
    """

    vcost: int = 0


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

    def get_variation(self, syllables: list[str] | None) -> list[list[str]]:
        """カナ発音のバリエーションを取得する(getVariation)。

        各変種に変換操作回数(コスト)を付与する(#105)。ン→ー化・ッ削除・
        裸ン/ッ削除・ー削除=各1操作、複合音節は合計、無変換や表記ゆれ
        (母音連続→ー)=0。返り値は従来同様のユニット配列(文字列配列)だが、
        各配列(Variation)に .vcost 属性で操作回数の合計を持たせる。
        variation の各要素は {"u": ユニット配列, "c": 操作数}。
        """
        result: list[list[dict[str, Any]]] = []
        if not syllables:
            return []
        for syllable in syllables:
            if syllable is None:
                continue
            variation: list[dict[str, Any]] = []
            if re.match(r"^[アイウエオ]$", syllable):  # アイウエオは先に処理
                variation.append({"u": [syllable], "c": 0})
            elif re.match(r"^[ンッ]$", syllable):
                variation.append({"u": [syllable], "c": 0})
                variation.append({"u": [""], "c": 1})  # 裸ン・ッの削除
            elif syllable == "ンー":  # ンー→["ン","ン"],["ン"],[""]
                variation.append({"u": ["ン", "ン"], "c": 1})  # ー→ン変換
                variation.append({"u": ["ン"], "c": 1})  # ー削除
                variation.append({"u": [""], "c": 2})  # ン削除+ー削除
            elif syllable == "ンッ":  # ンッ→["ン","ッ"],["ン"],["ッ"],[""]
                variation.append({"u": ["ン", "ッ"], "c": 0})
                variation.append({"u": ["ン"], "c": 1})  # ッ削除
                variation.append({"u": ["ッ"], "c": 1})  # ン削除
                variation.append({"u": [""], "c": 2})
            elif syllable.endswith("ーン"):  # ex: アーン→["アー","ン"],["アー"]
                head = syllable[:-2]
                variation.append({"u": [head + "ー", "ン"], "c": 0})
                variation.append({"u": [head + "ー"], "c": 1})  # ン削除
            elif syllable.endswith("ンッ"):  # ex: アンッ→[...]
                head = syllable[:-2]
                variation.append({"u": [head, "ン", "ッ"], "c": 0})
                variation.append({"u": [head, "ン"], "c": 1})  # ッ削除
                variation.append({"u": [head + "ー", "ッ"], "c": 1})  # ン→ー化
                variation.append({"u": [head + "ー"], "c": 2})  # ン→ー化+ッ削除
                variation.append({"u": [head, "ッ"], "c": 1})  # ン削除
            elif syllable.endswith("ーッ"):  # ex. アーッ→["アー","ッ"],["アー"]
                head = syllable[:-2]
                variation.append({"u": [head + "ー", "ッ"], "c": 0})
                variation.append({"u": [head + "ー"], "c": 1})  # ッ削除
            elif syllable.endswith("ー"):  # ex. アー→["アー"]
                head = syllable[:-1]
                variation.append({"u": [head + "ー"], "c": 0})
            elif syllable.endswith("ッ"):
                head = syllable[:-1]
                variation.append(
                    {"u": [head, "ッ"], "c": 0}
                )  # ex. アッ→["ア","ッ"],["ア"],["アー"]
                variation.append({"u": [head], "c": 1})  # ッ削除
                variation.append({"u": [head + "ー"], "c": 1})  # ッ→ー置換(単一操作でッ↔ーを閉じる)
            elif syllable.endswith("ン"):  # ex. アン→["ア","ン"],["アー"],["ア"]
                head = syllable[:-1]
                variation.append({"u": [head, "ン"], "c": 0})
                variation.append({"u": [head + "ー"], "c": 1})  # ン→ー化
                variation.append({"u": [head], "c": 1})  # ン削除(単一操作でン削除を閉じる)
            elif re.search(r"[アイウエオ]$", syllable):  # カア→["カ","ア"],["カー"]
                head = syllable[:-1]
                vowel = syllable[len(syllable) - 1]
                variation.append({"u": [head, vowel], "c": 0})
                variation.append(
                    {"u": [head + "ー"], "c": 0}
                )  # 表記ゆれ(母音連続→ー)扱いで無コスト
            else:  # 1モーラ
                variation.append({"u": [syllable], "c": 0})
            result.append(variation)

        out: list[list[str]] = []
        for combo in product(*result):
            # JSの v.flatMap(o=>o.u).filter(v2=>v2!=="")。空ユニットは平坦化後に除外
            flat = Variation(x for e in combo for x in e["u"] if x != "")
            if len(flat) != 0:
                flat.vcost = sum(e["c"] for e in combo)  # 操作回数の合計
                out.append(flat)
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

    def get_pronunciation_variation(self, syllables: list[str] | None) -> list[list[str]]:
        return self._k2s.get_variation(syllables)

    is_same_kana = staticmethod(is_same_kana)
    is_same_vowel = staticmethod(is_same_vowel)
    is_same_consonant = staticmethod(is_same_consonant)
    is_same_bar = staticmethod(is_same_bar)
    is_same_hatsuon = staticmethod(is_same_hatsuon)
    is_same_sokuon = staticmethod(is_same_sokuon)


def create_kana_converter(kana2phonon: dict[str, Any]) -> KanaConverter:
    return KanaConverter(kana2phonon)
