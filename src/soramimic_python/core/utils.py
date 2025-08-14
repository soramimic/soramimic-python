#!/usr/bin/env python3
"""
utils.py - ユーティリティ関数群
"""

import json
import random
import re
import string
from itertools import product as itertools_product
from pathlib import Path

import jaconv


def zip_arrays(*rows):
    """複数の配列をzip"""
    return list(zip(*rows, strict=False))


def product(*arguments):
    """直積を求めてリストで返す"""
    if len(arguments) == 0:
        return []

    # itertools.productを使って簡潔に実装
    return [list(item) for item in itertools_product(*arguments)]


def org_round(value: float, base: int) -> float:
    """指定した桁数で丸める"""
    return round(value * base) / base


def get_random_text(num: int = 8) -> str:
    """ランダムな文字列を生成"""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(num))  # nosec B311


def set_default_parameters(param: dict | None = None) -> dict:
    """デフォルトパラメータを設定"""
    default_param = {
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
    """全角から半角への変換"""
    # jaconvを使用して全角を半角に変換
    return jaconv.z2h(str_val, kana=False, ascii=True, digit=True)


def remove_sign(str_val: str) -> str:
    """記号を削除"""
    str_val = to_half_width(str_val)
    # 記号を削除（日本語文字以外）
    str_val = re.sub(r"[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]", "", str_val)
    # 特定の記号を削除
    str_val = str_val.replace("・", "").replace("「", "").replace("」", "")
    str_val = str_val.replace("。", "").replace("、", "")
    return str_val


def to_katakana(str_val: str) -> str:
    """ひらがなをカタカナに変換"""
    return jaconv.hira2kata(str_val)


def format_text(str_val: str) -> str:
    """テキストをフォーマット"""
    str_val = remove_sign(str_val)
    str_val = to_katakana(str_val)
    return str_val


def argsort(array: list) -> list[int]:
    """配列のソート順インデックスを返す"""
    indexed = [(val, idx) for idx, val in enumerate(array)]
    indexed.sort(key=lambda x: x[0])
    return [idx for _, idx in indexed]


def argmin(array: list) -> int:
    """最小値のインデックスを返す"""
    return min(enumerate(array), key=lambda x: x[1])[0]


def contain_alphabet(val: str) -> bool:
    """アルファベットが含まれているか判定"""
    return bool(re.search(r"[a-zA-Z]", val))


def load_json_file(path: str) -> dict:
    """JSONファイルを読み込む"""
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def load_text_file(path: str) -> str:
    """テキストファイルを読み込む"""
    with Path(path).open(encoding="utf-8") as f:
        return f.read()


def save_json_file(path: str, data: dict):
    """JSONファイルを保存"""
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_text_file(path: str, text: str):
    """テキストファイルを保存"""
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(text)
