# 移植元: frontend/src/lib/utils.js
"""utils.js からの移植(ロジック無改変)。

JSの ``zip`` は行方向の転置、``product`` は直積(リストのリスト)を返す。
本モジュールでは実際に使用される関数のみ移植する。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def product(*args: list[Any]) -> list[list[Any]]:
    """複数リストの直積を求めてリストで返す(utils.js の product 相当)。"""
    if len(args) == 0:
        return []
    prod: list[list[Any]] = [[m] for m in args[0]]
    for i in range(1, len(args)):
        new_prod: list[list[Any]] = []
        for m in prod:
            for n in args[i]:
                new_prod.append([*m, n])
        prod = new_prod
    return prod


def org_round(value: float, base: float) -> float:
    return round(value * base) / base


def set_default_parameters(param: dict[str, Any] | None = None) -> dict[str, Any]:
    """makeKanaDist時のデフォルトパラメータを作る(utils.js の setDefaultParameters)。"""
    default_param: dict[str, Any] = {
        "splitter": "/",
        "vowel": 1,
        "consonant": 1,
        "repeat": 100,
        "duplicate": False,
        "bunsetsu": 1,
        "wordsNum": 1,
        "sameChar": 1,
        "sameVowel": 1,
        "sameConsonant": 1,
        "length": 1,
    }
    if param:
        default_param.update(param)
    return default_param


def to_half_width(str_val: str) -> str:
    """全角の英数記号を半角に変換して返す(utils.js の toHalfWidth)。"""

    def _shift(m: re.Match[str]) -> str:
        return chr(ord(m.group(0)) - 0xFEE0)

    # 半角変換(！-～)
    half_val = re.sub(r"[！-～]", _shift, str_val)
    # 文字コードシフトで対応できない文字の変換
    return (
        half_val.replace("”", '"')
        .replace("’", "'")
        .replace("‘", "`")
        .replace("￥", "\\")
        .replace("　", " ")
        .replace("〜", "~")
    )


def remove_sign(str_val: str) -> str:
    """記号を削除する(utils.js の removeSign)。

    JSの ``\\W`` は ``[^A-Za-z0-9_]`` (ASCII語)であり日本語文字も含む。Pythonでは
    ``re.ASCII`` を付けて同じ挙動にする。ASCII記号・空白のみ削除し、日本語文字は残す。
    """
    str_val = to_half_width(str_val)  # 全角を半角に変換

    def _repl(m: re.Match[str]) -> str:
        ch = m.group(0)
        return "" if re.match(r"[!-~]|\s", ch) else ch

    str_val = re.sub(r"\W", _repl, str_val, flags=re.ASCII)
    str_val = str_val.replace("・", "").replace("「", "").replace("」", "")
    str_val = str_val.replace("。", "").replace("、", "")
    return str_val


def to_katakana(str_val: str) -> None:
    """utils.js の toKatakana を忠実に移植。

    JS版は replace の結果を返さず、副作用も無いため何もしない(戻り値 undefined)。
    """
    # JSの toKatakana は replace 結果を捨てており、実質何もしない
    return None


def format_text(str_val: str) -> str | None:
    """utils.js の formatText を忠実に移植(toKatakana が None を返す点も含む)。"""
    str_val = remove_sign(str_val)
    str_val = to_katakana(str_val)  # type: ignore[assignment]
    return str_val


def argsort(array: list[Any]) -> list[int]:
    """安定な argsort(utils.js の argsort)。"""
    indexed = sorted(range(len(array)), key=lambda i: array[i])
    return indexed


def argmin(array: list[Any]) -> int:
    """最小値のインデックスを返す(utils.js の argmin)。"""
    best_i = 0
    for i in range(1, len(array)):
        if array[i] < array[best_i]:
            best_i = i
    return best_i


def find_min(array: list[T], get_value: Callable[[T], Any]) -> T | None:
    """配列から get_value が最小の要素を返す(soramimic.js の getMin 相当)。

    最初に見つかった最小値(狭義 <)の要素を返す。空配列なら None。
    """
    minimum: Any = float("inf")
    content: T | None = None
    for v in array:
        val = get_value(v)
        if val < minimum:
            content = v
            minimum = val
    return content


def is_array_index(key: str) -> bool:
    """JSのオブジェクトで「配列インデックス」とみなされる文字列キーか判定。"""
    if not key.isdigit():
        return False
    if len(key) > 1 and key[0] == "0":
        return False
    return int(key) < 2**32 - 1


def js_object_key_order(keys: list[str]) -> list[str]:
    """JSオブジェクトのキー列挙順を再現する。

    整数風文字列キーは数値昇順、その他は挿入順(与えられた順)。
    """
    int_keys = [k for k in keys if is_array_index(k)]
    other_keys = [k for k in keys if not is_array_index(k)]
    int_keys.sort(key=int)
    return int_keys + other_keys
