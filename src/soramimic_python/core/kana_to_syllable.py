"""カナから音節への変換モジュール.

このモジュールはカナ文字を音節単位に分割し、
発音のバリエーションを生成する機能を提供します。
"""

import logging
import re
from itertools import product

# ロガーの設定
logger = logging.getLogger(__name__)


def bar_to_vowel(text: str) -> str:
    """長音記号を母音に変換する.

    Args:
        text: 変換対象のテキスト

    Returns:
        変換後のテキスト
    """

    def replace_func(match):
        first = match.group(0)[0]
        vowel = char_to_vowel(first)
        if first == "ン":
            vowel = "ン"  # ンは特別扱い
        elif first == "ッ":
            vowel = "ッ"  # ッも特別扱い
        return first + vowel

    return re.sub(r"[ァ-ンヴ]ー", replace_func, text)


def vowel_to_bar(text: str) -> str:
    """母音を長音記号に変換する.

    Args:
        text: 変換対象のテキスト

    Returns:
        変換後のテキスト
    """

    def replace_func(match):
        first = match.group(0)[0]
        vowel = char_to_vowel(first)
        res = match.group(0)
        if (
            vowel == match.group(0)[1]
            or (vowel == "エ" and match.group(0)[1] == "イ")
            or (vowel == "オ" and match.group(0)[1] == "ウ")
        ):
            res = first + "ー"
        return res

    return re.sub(r"[ァ-ンヴ][アイウエオ]", replace_func, text)


def char_to_consonant(char: str) -> str:
    """文字を子音に変換する.

    Args:
        char: 変換対象の文字

    Returns:
        子音
    """
    cols = {
        "sp": "アイウエオヲーンッ",
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
    }

    first = char[0] if char else ""
    consonant = ""
    for c, col in cols.items():
        if first in col:
            consonant = c
            break
    return consonant


def is_same_kana(kana1: str, kana2: str) -> bool:
    """同じ文字か判定."""
    return kana1 == kana2


def is_same_vowel(kana1: str, kana2: str) -> bool:
    """同じ母音か判定."""
    v1 = char_to_vowel(kana1)
    v2 = char_to_vowel(kana2)
    return v1 == v2


def is_same_consonant(kana1: str, kana2: str) -> bool:
    """同じ子音か判定."""
    c1 = char_to_consonant(kana1)
    c2 = char_to_consonant(kana2)
    return c1 == c2


def is_same_bar(kana1: str, kana2: str) -> bool:
    """どちらも長音かどうか."""
    check_char = "ー"
    is_kana1_ok = kana1.endswith(check_char)
    is_kana2_ok = kana2.endswith(check_char)
    return is_kana1_ok and is_kana2_ok


def is_same_sokuon(kana1: str, kana2: str) -> bool:
    """どちらも促音かどうか."""
    check_char = "ッ"
    is_kana1_ok = kana1.endswith(check_char)
    is_kana2_ok = kana2.endswith(check_char)
    return is_kana1_ok and is_kana2_ok


def is_same_hatsuon(kana1: str, kana2: str) -> bool:
    """どちらも撥音かどうか."""
    check_char = "ン"
    is_kana1_ok = kana1.endswith(check_char)
    is_kana2_ok = kana2.endswith(check_char)
    return is_kana1_ok and is_kana2_ok


def hira_to_kata(text: str) -> str:
    """ひらがなをカタカナに変換."""
    result = ""
    for char in text:
        if "\u3041" <= char <= "\u3096":
            result += chr(ord(char) + 0x60)
        else:
            result += char
    return result


class KanaPattern:
    """日本語のカナの正規表現パターンを生成するクラス.

    日本語の場合、「ファ」などのように２文字で１モーラを構成するカナがあることに注意。
    """

    @staticmethod
    def get_patterns() -> dict[str, str]:
        """ア段からオ段の音パターンを取得."""
        # ア段からオ段までの1文字カナ集合と「テ」「デ」の集合を定義
        kana_a = "[アカサタナハマヤラワガザダバパ]"
        kana_i = "[イキシチニヒミリギジヂビピ]"
        kana_i2 = kana_i.replace("イ", "")  # ャュョとくっつける用のイ段
        kana_u = "[ウクスツヌフムユルグズヅブプヴ]"
        kana_e = "[エケセテネヘメレゲゼデベペ]"
        kana_o = "[オコソトノホモヨロヲゴゾドボポ]"
        kana_td = "[テデ]"

        # ２文字で１モーラになるカナの定義
        kana_multi_a = f"({kana_u}[ァヮ]|{kana_i2}ャ|{kana_td}ャ)"
        kana_multi_i = f"({kana_u}ィ|{kana_td}ィ)"
        kana_multi_u = f"({kana_i}ュ|{kana_td}ュ|[トド]ゥ)"
        kana_multi_e = f"({kana_u}ェ|{kana_i}ェ)"
        kana_multi_o = f"({kana_u}ォ|{kana_i2}ョ)"
        kana_multi = (
            f"({kana_u}[ァィェォ]|{kana_td}[ャィュョ]|"
            f"{kana_i}[ャュョ]|{kana_i2}ェ|[トド]ゥ)"
        )

        # ンーッと小文字を除くカナ
        kana_single_base = "[アイウエオ-ヂツ-モヤユヨ-ロワヲヴ]"
        # ２文字で１モーラとなるカナも含めた全カナ集合(ー/ン/ッと小文字単体は除く)の定義
        kana_base = f"({kana_multi}|{kana_single_base})"
        # ２文字で１モーラとなるカナも含めた全カナ集合(ー/ン/ッと小文字単体も含む)の定義
        kana_all = f"({kana_multi}|[ァ-ヴー])"

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


def char_to_vowel(char: str) -> str:
    """文字を母音に変換する.

    Args:
        char: 変換対象の文字

    Returns:
        母音
    """
    if char == "ー":
        logger.warning("warning: only ー is input")
        return char

    # 伸ばし棒を除いた末尾の文字を取得
    last = ""
    for i in range(len(char) - 1, -1, -1):
        last = char[i]
        if last != "ー":
            break

    rows = {
        "ア": "アカサタナハマヤラワガザダバパァャヮ",
        "イ": "イキシチニヒミリギジヂビピィ",
        "ウ": "ウクスツヌフムユルグズヅブプヴゥュ",
        "エ": "エケセテネヘメレゲゼデベペェ",
        "オ": "オコソトノホモヨロゴゾドボポォ",
        "sp": "ンッ",
    }

    vowel = last
    for v, row in rows.items():
        if last in row:
            vowel = v
            break
    return vowel


def small_vowel_to_bar(text: str) -> str:
    """小文字母音を長音に変換する.

    Args:
        text: 変換対象のテキスト

    Returns:
        変換後のテキスト
    """
    # 長音のうしろの小文字母音を長音に
    replaced_text = re.sub(r"ー(ァ+|ィ+|ゥ+|ェ+|ォ+)", "ー", text)

    # 同じ母音のカナの後ろの小文字母音を長音に
    def replace_func(match):
        res = match.group(0)
        l2s = {"ア": "ァ", "イ": "ィ", "ウ": "ゥ", "エ": "ェ", "オ": "ォ"}
        # 1文字目の母音が2文字目の小文字母音と対応していたら
        first_vowel = char_to_vowel(match.group(0)[0])
        if first_vowel in l2s and l2s[first_vowel] == match.group(0)[1]:
            res = match.group(0)[0] + "ー"
        # 上記以外の小文字母音の連続に対応
        elif len(match.group(0)) >= 3:
            res = match.group(0)[0] + match.group(0)[1] + "ー"
        return res

    replaced_text = re.sub(r"[ァ-ヴ](ァ+|ィ+|ゥ+|ェ+|ォ+)", replace_func, replaced_text)
    return replaced_text


def small_vowel_to_large(text: str) -> str:
    """2文字カナの一部でない小文字(ッを除く)を大文字にする.

    Args:
        text: 変換対象のテキスト

    Returns:
        変換後のテキスト
    """
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

    # 先頭以外の置換
    def replace_func(match):
        match_text = match.group(0)
        if (
            re.match(r"[ウクスツヌフムユルグズヅブプヴ][ァヮォ]", match_text)
            or re.match(r"[トド]ゥ", match_text)
            or re.match(r"[キシチニヒミリギジヂビピテデ][ャュョ]", match_text)
            or re.match(r"[ウクスツヌフムユルグズヅブプヴテデ]ィ", match_text)
            or re.match(
                r"[ウクスツヌフムユルグズヅブプヴイキシチニヒミリギジヂビピ]ェ",
                match_text,
            )
        ):  # ウ段の後ろのァヮェォ
            return match_text
        else:
            for small, large in s2l.items():
                match_text = match_text.replace(small, large)
            return match_text

    replaced_text = re.sub(r".[ァィゥェォヮャュョ]", replace_func, text)

    # 先頭の置換
    def replace_head(match) -> str:
        char = match.group(0)
        return s2l[char] if char in s2l else char

    replaced_text = re.sub(
        r"^[ァィゥェォヮャュョ]", replace_head, replaced_text, flags=re.MULTILINE
    )
    return replaced_text


def remove_bar_and_sokuon_reputation(text: str) -> str:
    """ーとッの不自然な並びを削除する.

    Args:
        text: 変換対象のテキスト

    Returns:
        変換後のテキスト
    """
    text = re.sub(r"ー+", "ー", text)  # ーの連続を1文字にする
    text = re.sub(r"ッ[ーッ]+", "ッ", text)  # ッの後ろのーまたはッの連続を削除
    text = re.sub(r"^[ーッ]+", "", text)  # 先頭の[ーッ]を削除
    return text


def remove_unnatural_kana_pattern(text: str) -> str:
    """小文字や長音、促音の不自然な並びを解消する.

    Args:
        text: 変換対象のテキスト

    Returns:
        変換後のテキスト
    """
    text = small_vowel_to_bar(text)
    text = small_vowel_to_large(text)
    text = remove_bar_and_sokuon_reputation(text)
    return text


def mora_split(text: str) -> list[str]:
    """入力カナをモーラの単位で分かち書きする.

    Args:
        text: 分割対象のテキスト

    Returns:
        モーラ単位に分割されたリスト
    """
    pattern = (
        r"[ウクスツヌフムユルグズヅブプ][ァヮィェォ]|"
        r"[キシチニヒミリギジヂビピテデ][ャュョ]|"
        r"[イキシチニヒミリギジヂビピ]ェ|[テデ]ィ|[トド]ゥ|[ァ-ヴー]"
    )
    matches = re.findall(pattern, text)
    return matches


class KanaToMora:
    """カナをモーラに変換するクラス."""

    def __init__(self):
        self.pattern = (
            r"[ウクスツヌフムユルグズヅブプ][ァヮィェォ]|"
            r"[キシチニヒミリギジヂビピテデ][ャュョ]|"
            r"[イキシチニヒミリギジヂビピ]ェ|[テデ]ィ|[トド]ゥ|[ァ-ヴー]"
        )

    def split(self, text: str) -> list[str]:
        """テキストをモーラ単位に分割."""
        return re.findall(self.pattern, text)


class KanaToSyllable:
    """カナを音節に変換するクラス."""

    def __init__(self):
        # よく使うカナパターンの取得
        kana = KanaPattern.get_patterns()

        # ーンッを前のカナとつなげるときのパターン
        re2 = r"ーッ|ンッ|ーン(?![ーッ])"  # ーンは後ろにーッが来るとき以外
        re1 = r"ー|ッ|ン(?!ー)"  # ンは後ろに長音が来るとき以外
        re_back = f"({re2}|{re1})"

        # 長いものからマッチする
        # ２文字カナとーンッのマッチ
        re_multi_bar = f"({kana['multi']}{re_back})"

        # 2文字カナと母音のマッチ
        re_multi_a = kana["multi_a"] + "ア"
        re_multi_i = kana["multi_i"] + "イ(?![ェ])"
        re_multi_u = kana["multi_u"] + "ウ(?![ァィェォ])"
        re_multi_e = kana["multi_e"] + "[エイ]"
        re_multi_o = kana["multi_o"] + "(オ|ウ(?![ァィェォ]))"
        re_multi_vowel = (
            f"({re_multi_a}|{re_multi_i}|{re_multi_u}|{re_multi_e}|{re_multi_o})"
        )
        re_multi_vowel += "(?![ーンッ])"

        # ２文字カナ単独のマッチ
        re_multi_unit = kana["multi"]

        # ンとーッのマッチ
        re_n_bar = "ン([ーッ]|ーッ)"

        # １文字カナとーッンのマッチ
        re_single_bar = f"({kana['single_base']}{re_back})"

        # １文字カナと母音のマッチ
        re_single_a = kana["single_a"] + "ア"
        re_single_i = kana["single_i"] + "イ"
        re_single_u = kana["single_u"] + "ウ(?![ァィェォ])"
        re_single_e = kana["single_e"] + "[エイ]"
        re_single_o = kana["single_o"] + "(オ|ウ(?![ァィェォ]))"
        re_single_vowel = (
            f"({re_single_a}|{re_single_i}|{re_single_u}|{re_single_e}|{re_single_o})"
        )
        # 1文字カナ単独のマッチ
        re_single_vowel += "(?![ーンッ])"

        re_single_unit = "[ァ-ヴー]"

        # 上記で定義した条件のオアをとる
        self.re_all = re.compile(
            f"{re_multi_bar}|{re_multi_vowel}|{re_multi_unit}|{re_n_bar}|{re_single_bar}|{re_single_vowel}|{re_single_unit}"
        )

        # ２文字以上で１シラブルの組み合わせ
        re_multi_kana_full = (
            f"^({re_multi_bar}|{re_multi_vowel}|{re_multi_unit}|"
            f"{re_n_bar}|{re_single_bar}|{re_single_vowel})$"
        )
        self.re_multi_kana_full = re.compile(re_multi_kana_full)

    def is_fullmatch(self, text: str) -> bool:
        """２文字以上で１シラブルの組み合わせかチェック."""
        return bool(self.re_multi_kana_full.match(text))

    def split(self, text: str) -> list[str]:
        """テキストを音節単位に分割."""
        matches = self.re_all.findall(text)
        # findallは複数のキャプチャグループがある場合にタプルを返すので、
        # 空でない最初の要素を取得
        result = []
        for match in matches:
            if isinstance(match, tuple):
                # タプルの場合は、空でない最初の要素を取得
                for item in match:
                    if item:
                        result.append(item)
                        break
                else:
                    # すべてが空文字列の場合は、元のマッチ全体を取得
                    # これは正規表現のマッチした全体文字列を取得する方法
                    pass
            elif match:
                result.append(match)

        # より確実な方法: 正規表現を使って直接マッチした部分を取得
        if not result or len(result) != len([m for m in self.re_all.finditer(text)]):
            # findallがうまく動作しない場合は、finditerを使用
            result = []
            for match_obj in self.re_all.finditer(text):
                result.append(match_obj.group(0))

        return result

    def get_variation(self, syllables: list[str]) -> list[list[str]]:
        """カナの発音のバリエーションを取得する."""
        if not syllables:
            return []

        result = []
        for syllable in syllables:
            variation = []

            # アイウエオは先に処理しておく
            if re.match(r"^[アイウエオ]$", syllable):
                variation.append([syllable])
            elif re.match(r"^[ンッ]$", syllable):
                variation.append([syllable])
                variation.append([""])
            elif syllable == "ンー":  # ンー→["ン","ン"],["ン"],[""]
                variation.append(["ン", "ン"])
                variation.append(["ン"])
                variation.append([""])
            elif syllable == "ンッ":  # ンッ→["ン","ッ"],["ン"],["ッ"],[""]
                variation.append(["ン", "ッ"])
                variation.append(["ン"])
                variation.append(["ッ"])
                variation.append([""])
            elif syllable.endswith("ーン"):  # ex: アーン→["アー","ン"],["アー"]
                head = syllable[:-2]
                variation.append([head + "ー", "ン"])
                variation.append([head + "ー"])
            elif syllable.endswith(
                "ンッ"
            ):  # ex: アンッ→["ア","ン","ッ"],["ア","ン"],["アー","ッ"],["アー"]
                head = syllable[:-2]
                variation.append([head, "ン", "ッ"])
                variation.append([head, "ン"])
                variation.append([head + "ー", "ッ"])
                variation.append([head + "ー"])
            elif syllable.endswith("ーッ"):  # ex. アーッ→["アー","ッ"],["アー"]
                head = syllable[:-2]
                variation.append([head + "ー", "ッ"])
                variation.append([head + "ー"])
            elif syllable.endswith("ー"):  # ex. アー→["アー"]
                head = syllable[:-1]
                variation.append([head + "ー"])
            elif syllable.endswith("ッ"):
                head = syllable[:-1]
                variation.append([head, "ッ"])  # ex. アッ→["ア","ッ"],["ア"]
                variation.append([head])
            elif syllable.endswith("ン"):  # ex. アン→["ア","ン"],["アー"]
                head = syllable[:-1]
                variation.append([head, "ン"])
                variation.append([head + "ー"])
            # 母音で終わる
            elif re.search(r"[アイウエオ]$", syllable):  # カア→["カ","ア"],["カー"]
                head = syllable[:-1]
                vowel = syllable[-1]
                variation.append([head, vowel])
                variation.append([head + "ー"])
            # 1モーラ
            else:
                variation.append([syllable])

            result.append(variation)

        # 直積を計算し、フィルタリング
        all_combinations = list(product(*result))
        filtered_combinations = []

        for combination in all_combinations:
            # 空文字列を除去して平坦化
            flattened = [
                item for sublist in combination for item in sublist if item != ""
            ]
            if len(flattened) > 0:  # 長さ0の配列は要素に含めない
                filtered_combinations.append(flattened)

        return filtered_combinations


def zip_lists(list1: str, list2: str) -> list[tuple[str, str]]:
    """2つの文字列を文字単位でペアにする."""
    return list(zip(list1, list2, strict=False))


def get_kana_to_vowel_dictionary(
    kana2phonon_dictionary: dict[str, list[str]],
) -> dict[str, str]:
    """カナから母音への辞書を生成する.

    Args:
        kana2phonon_dictionary: カナから音韻への辞書

    Returns:
        カナから母音への辞書
    """
    k2r = kana2phonon_dictionary

    # ローマ字母音をカタカナ母音にマッピング
    roma2vowel = dict(zip_lists("aiueo", "アイウエオ"))
    roma2vowel["p"] = "sp"  # 無音
    roma2vowel["N"] = "sp"  # 撥音の母音は無音とする
    roma2vowel["q"] = "sp"  # 促音の母音は無音とする

    result = {}
    for kana in k2r:
        if len(k2r[kana]) > 1 and len(k2r[kana][1]) > 0:
            # kanaのローマ字表記の最後の文字(=母音)を取得
            roma_vowel_of_kana = k2r[kana][1][-1]
            result[kana] = roma2vowel.get(roma_vowel_of_kana, roma_vowel_of_kana)

        # 追加のバリエーション
        if kana in "ンッ" or kana == "sp":
            pass
        elif kana in result:
            result[kana + "ー"] = result[kana]
            if result[kana] == "エ":
                result[kana + "イ"] = result[kana]
            elif result[kana] == "オ":
                result[kana + "ウ"] = result[kana]

    return result


def phonon_split(text: str) -> list[str]:
    """phononの単位でsplitする.

    ン、ッは１単位。ーと母音だけ直前カナと１単位とみなす

    Args:
        text: 分割対象のテキスト

    Returns:
        phonon単位に分割されたリスト
    """
    kana = KanaPattern.get_patterns()

    # 長いものからマッチする
    # ２文字カナとーのマッチ
    re_multi_bar = f"({kana['multi']}ー)"

    # 2文字カナと母音のマッチ
    re_multi_a = kana["multi_a"] + "ア"
    re_multi_i = kana["multi_i"] + "イ(?![ェ])"
    re_multi_u = kana["multi_u"] + "ウ(?![ァィェォ])"
    re_multi_e = kana["multi_e"] + "[エイ]"
    re_multi_o = kana["multi_o"] + "(オ|ウ(?![ァィェォ]))"
    re_multi_vowel = (
        f"({re_multi_a}|{re_multi_i}|{re_multi_u}|{re_multi_e}|{re_multi_o})"
    )
    re_multi_vowel += "(?!ー)"

    # ２文字カナ単独のマッチ
    re_multi_unit = kana["multi"]

    # ンとーッのマッチ
    re_n_bar = "ンー"

    # １文字カナとーッンのマッチ
    re_single_bar = f"({kana['single_base']}ー)"

    # １文字カナと母音のマッチ
    re_single_a = kana["single_a"] + "ア"
    re_single_i = kana["single_i"] + "イ"
    re_single_u = kana["single_u"] + "ウ(?![ァィェォ])"
    re_single_e = kana["single_e"] + "[エイ]"
    re_single_o = kana["single_o"] + "(オ|ウ(?![ァィェォ]))"
    re_single_vowel = (
        f"({re_single_a}|{re_single_i}|{re_single_u}|{re_single_e}|{re_single_o})"
    )
    # 1文字カナ単独のマッチ
    re_single_vowel += "(?!ー)"

    re_single_unit = "[ァ-ヴー]"
    # 上記で定義した条件のオアをとる
    pattern = (
        f"{re_multi_bar}|{re_multi_vowel}|{re_multi_unit}|"
        f"{re_n_bar}|{re_single_bar}|{re_single_vowel}|{re_single_unit}"
    )

    # matchで抽出
    matches = re.findall(pattern, text)
    return matches


class KanaConverter:
    """カナ変換器クラス."""

    def __init__(self, kana2phonon_data: dict[str, list[str]] | None = None):
        """初期化.

        Args:
            kana2phonon_data: カナから音韻への辞書データ
        """
        # デフォルトのkana2phonon辞書（簡易版）
        if kana2phonon_data is None:
            kana2phonon_data = self._get_default_kana2phonon()

        self.KANA2PHONON_ = kana2phonon_data
        self.k2s = KanaToSyllable()

        self.KANA2VOWEL_ = get_kana_to_vowel_dictionary(self.KANA2PHONON_)
        logger.info(
            f"KanaConverter initialized with {len(self.KANA2VOWEL_)} vowel mappings"
        )

        # 子音辞書の生成
        self.KANA2CONSONANT_ = self._get_kana2consonant(self.KANA2PHONON_)

        # カナユニット辞書の生成
        self.KANA_UNITS_ = self._get_kana_units(self.KANA2PHONON_, self.KANA2VOWEL_)

    def _get_default_kana2phonon(self) -> dict[str, list[str]]:
        """デフォルトのkana2phonon辞書を生成."""
        # 簡易版の実装（本来はJSONファイルから読み込み）
        return {
            "ア": ["", "a"],
            "イ": ["", "i"],
            "ウ": ["", "u"],
            "エ": ["", "e"],
            "オ": ["", "o"],
            "カ": ["k", "ka"],
            "キ": ["k", "ki"],
            "ク": ["k", "ku"],
            "ケ": ["k", "ke"],
            "コ": ["k", "ko"],
            "サ": ["s", "sa"],
            "シ": ["s", "si"],
            "ス": ["s", "su"],
            "セ": ["s", "se"],
            "ソ": ["s", "so"],
            "タ": ["t", "ta"],
            "チ": ["t", "ti"],
            "ツ": ["t", "tu"],
            "テ": ["t", "te"],
            "ト": ["t", "to"],
            "ナ": ["n", "na"],
            "ニ": ["n", "ni"],
            "ヌ": ["n", "nu"],
            "ネ": ["n", "ne"],
            "ノ": ["n", "no"],
            "ハ": ["h", "ha"],
            "ヒ": ["h", "hi"],
            "フ": ["h", "hu"],
            "ヘ": ["h", "he"],
            "ホ": ["h", "ho"],
            "マ": ["m", "ma"],
            "ミ": ["m", "mi"],
            "ム": ["m", "mu"],
            "メ": ["m", "me"],
            "モ": ["m", "mo"],
            "ヤ": ["y", "ya"],
            "ユ": ["y", "yu"],
            "ヨ": ["y", "yo"],
            "ラ": ["r", "ra"],
            "リ": ["r", "ri"],
            "ル": ["r", "ru"],
            "レ": ["r", "re"],
            "ロ": ["r", "ro"],
            "ワ": ["w", "wa"],
            "ヲ": ["w", "wo"],
            "ン": ["N", "N"],
            "ッ": ["q", "q"],
            "ー": ["", ""],
            "sp": ["sp", "sp"],
        }

    def _get_kana2consonant(self, kana2phonon: dict[str, list[str]]) -> dict[str, str]:
        """カナから子音への辞書を生成."""
        result = {}
        for kana, phonon in kana2phonon.items():
            if len(phonon) > 0:
                roma_consonant = phonon[0] if phonon[0] != "sp" else "sp"
                if roma_consonant == "c":
                    result[kana] = "t"  # cはtと同じ子音とする
                elif roma_consonant == "f":
                    result[kana] = "h"  # fはhと同じ子音とする
                elif roma_consonant == "j":
                    result[kana] = "z"  # jはzと同じ子音とする
                elif roma_consonant == "v":
                    result[kana] = "b"  # vはbと同じ子音とする
                else:
                    result[kana] = roma_consonant
        return result

    def _get_kana_units(
        self, kana2phonon: dict[str, list[str]], kana2vowel: dict[str, str]
    ) -> dict[str, list[list[str]]]:
        """カナユニット辞書を生成."""
        result = {}
        for kana in kana2phonon:
            vowel_of_kana = kana2vowel.get(kana, "")
            result[kana] = [[kana]]

            if kana in ["ン", "ッ"]:
                result[kana].append([""])

            if vowel_of_kana in ["ア", "イ", "ウ", "エ", "オ"]:
                result[kana + "ー"] = [[kana + "ー"]]  # 伸ばし棒のユニットを追加
                result[kana + "ン"] = [[kana + "ン"]]  # ンのユニットを追加
                result[kana + "ッ"] = [[kana + "ッ"]]  # ッのユニットを追加
                result[kana + vowel_of_kana] = [
                    [kana + "ー"],
                    [kana, vowel_of_kana],
                ]  # 母音の連続を伸ばし棒化
                if vowel_of_kana == "エ":
                    result[kana + "イ"] = [
                        [kana + "ー"],
                        [kana, "イ"],
                    ]  # eiを伸ばし棒化
                if vowel_of_kana == "オ":
                    result[kana + "ウ"] = [
                        [kana + "ー"],
                        [kana, "ウ"],
                    ]  # ouを伸ばし棒化

        return result

    def separate(self, kana_str: str) -> list[str]:
        """カナ文字列を音節に分離."""
        return self.k2s.split(kana_str)

    @staticmethod
    def is_same_kana(kana1: str, kana2: str) -> bool:
        """同じ文字か判定."""
        return is_same_kana(kana1, kana2)

    @staticmethod
    def is_same_vowel(kana1: str, kana2: str) -> bool:
        """同じ母音か判定."""
        return is_same_vowel(kana1, kana2)

    @staticmethod
    def is_same_consonant(kana1: str, kana2: str) -> bool:
        """同じ子音か判定."""
        return is_same_consonant(kana1, kana2)

    @staticmethod
    def is_same_bar(kana1: str, kana2: str) -> bool:
        """どちらも長音か判定."""
        return is_same_bar(kana1, kana2)

    @staticmethod
    def is_same_hatsuon(kana1: str, kana2: str) -> bool:
        """どちらも撥音か判定."""
        return is_same_hatsuon(kana1, kana2)

    @staticmethod
    def is_same_sokuon(kana1: str, kana2: str) -> bool:
        """どちらも促音か判定."""
        return is_same_sokuon(kana1, kana2)


# メイン実装のインスタンス
kana_converter = KanaConverter()


# 公開関数（下位互換性のため）
def separate(text: str) -> list[str]:
    """カナ文字列を音節に分離する（下位互換性用）."""
    return kana_converter.separate(text)


def get_pronunciation_variation(syllables: list[str]) -> list[list[str]]:
    """発音のバリエーションを取得する（下位互換性用）."""
    return kana_converter.get_pronunciation_variation(syllables)


__all__ = [
    "KanaConverter",
    "KanaPattern",
    "KanaToMora",
    "KanaToSyllable",
    "char_to_consonant",
    "char_to_vowel",
    "get_pronunciation_variation",
    "hira_to_kata",
    "is_same_bar",
    "is_same_consonant",
    "is_same_hatsuon",
    "is_same_kana",
    "is_same_sokuon",
    "is_same_vowel",
    "kana_converter",
    "mora_split",
    "phonon_split",
    "remove_bar_and_sokuon_reputation",
    "remove_unnatural_kana_pattern",
    "separate",
    "small_vowel_to_bar",
    "small_vowel_to_large",
]

if __name__ == "__main__":
    k2s = KanaToSyllable()
    print(k2s.split("カタカナ"))  # カタカナを音節に分割
