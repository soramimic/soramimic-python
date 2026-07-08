# トークナイザのプロトコル定義。
"""トークナイザ抽象。

トークン dict のキーは kuromojiTokenizer.js / mecabTokenizer.js 準拠:
surface_form, basic_form, reading, pronunciation, pos, pos_detail_1..3,
conjugated_form, conjugated_type, word_position。未知は "*"。

tokenize(text) は 1 文字列ならトークン列、文字列リストならトークン列のリストを返す。
get_yomi(text) は既知語=読み・未知語=表層を連結した読み文字列(リストならリスト)を返す。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

Token = dict[str, Any]


@runtime_checkable
class Tokenizer(Protocol):
    def tokenize(self, text: str | list[str]) -> list[Token] | list[list[Token]]: ...

    def get_yomi(self, text: str | list[str]) -> str | list[str]: ...
