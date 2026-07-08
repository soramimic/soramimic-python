"""テスト用の共通ヘルパ(fake トークナイザ等)。"""

from __future__ import annotations

from typing import Any

Token = dict[str, Any]


def make_token(surface: str, pronunciation: str = "*", pos: str = "名詞") -> Token:
    """1トークンを表す dict を作る(kuromoji 準拠キー)。"""
    return {
        "surface_form": surface,
        "basic_form": surface,
        "reading": "*",
        "pronunciation": pronunciation,
        "pos": pos,
        "pos_detail_1": "一般",
        "pos_detail_2": "*",
        "pos_detail_3": "*",
        "conjugated_form": "*",
        "conjugated_type": "*",
        "word_position": 1,
    }


def single_token_tokenizer(texts: list[str]) -> list[list[Token]]:
    """各文字列を1トークンにするだけの fake(pronunciation は "*")。"""
    return [[make_token(t)] for t in texts]


def fixed_yomi(text: Any) -> Any:
    """漢字読み推定 fake。リストならそのまま(表層=読み扱い)返す。"""
    return list(text) if isinstance(text, list) else text
