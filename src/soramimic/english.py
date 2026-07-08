# 移植元: frontend/src/lib/english.js
"""english.js からの移植(ロジック無改変)。

英単語・ローマ字・アルファベットをカナへ変換する。Apostrophe はアポストロフィを
プレースホルダ文字列 "APOSTROPHE" に退避/復元する。
"""

from __future__ import annotations

import re
from typing import Any

Token = dict[str, Any]


class Apostrophe:
    """english.js の Apostrophe()。"""

    STRING_APOSTROPHY = "APOSTROPHE"

    def to_string(self, text: str) -> str:
        # ’ と ' を共に APOSTROPHE に退避
        return text.replace("’", "'").replace("'", self.STRING_APOSTROPHY)

    def to_sign(self, text: str) -> str:
        return text.replace(self.STRING_APOSTROPHY, "'")

    def remove_string(self, text: str) -> str:
        return text.replace(self.STRING_APOSTROPHY, "")

    def include(self, text: str) -> bool:
        # JS原典は text.include(...) というタイポ(実行時エラー)。移植では includes 相当。
        return self.STRING_APOSTROPHY in text

    def format(self, text: str) -> str:
        return re.sub(r"[’]", "'", text)


class English:
    """english.js の English(DICTIONARY, TREE)。"""

    def __init__(self, dictionary: dict[str, str], tree: dict[str, Any]) -> None:
        self.dictionary = dictionary
        self.tree = tree
        self.apostrophe = Apostrophe()

    @staticmethod
    def _zenkaku_english_to_hankaku(text: str) -> str:
        # JSは /g 無し = 最初の1マッチのみ置換
        return re.sub(r"[Ａ-Ｚａ-ｚ]", lambda m: chr(ord(m.group(0)) - 65248), text, count=1)

    @staticmethod
    def _roman_to_kana(text: str, tree: dict[str, Any]) -> str:
        s = text.lower()
        result = ""
        tmp = ""
        index = 0
        length = len(s)
        node: Any = tree

        def push(char: str, to_root: bool = True) -> None:
            nonlocal result, tmp, node
            result += char
            tmp = ""
            node = tree if to_root else node

        while index < length:
            char = s[index]
            if re.match(r"[a-z]", char):
                if char in node:
                    nxt = node[char]
                    if isinstance(nxt, str):
                        push(nxt)
                    else:
                        tmp += text[index]
                        node = nxt
                    index += 1
                    continue
                prev = s[index - 1] if index - 1 >= 0 else ""
                if prev and (prev == "n" or prev == char):  # 促音やnへの対応
                    push("ン" if prev == "n" else "ッ", False)
                if node is not tree and char in tree:  # ルート以外なら仕切り直す
                    push(tmp)
                    continue
            push(tmp + char)
            index += 1
        tmp = re.sub(r"n$", "ン", tmp)  # 末尾のnは変換する
        push(tmp)
        return result

    @staticmethod
    def _english_word_to_kana(text: str, dictionary: dict[str, str]) -> str:
        e2k = dictionary
        upper = text.upper()
        if upper in e2k:
            return e2k[upper]
        return text

    @staticmethod
    def _alphabet_to_kana(text: str, dictionary: dict[str, str]) -> str:
        e2k = dictionary
        text = text.upper()
        found = re.findall(r"[A-Z]", text)
        if found:
            for v in found:
                text = e2k[v].join(text.split(v))
        return text

    def _english_to_kana(self, text: str, dictionary: dict[str, str], tree: dict[str, Any]) -> str:
        text = self._zenkaku_english_to_hankaku(text)
        text = self._english_word_to_kana(text, dictionary)
        text = self._roman_to_kana(text, tree)
        text = self._alphabet_to_kana(text, dictionary)
        return text

    @staticmethod
    def is_fullmatch(text: str) -> bool:
        return re.match(r"^[a-zA-Z']+$", text) is not None

    def to_kana(self, text: str) -> str:
        return self._english_to_kana(text, self.dictionary, self.tree)

    def tokenize(self, text: str, tokenizer: Any) -> list[Token]:
        ap = self.apostrophe
        str_val = ap.to_string(text)
        tokens = tokenizer.tokenize(str_val)
        for token in tokens:
            if self.is_fullmatch(token["surface_form"]):
                token["surface_form"] = ap.to_sign(token["surface_form"])
                if token["pronunciation"] == "*":
                    token["pronunciation"] = self._english_to_kana(
                        token["surface_form"], self.dictionary, self.tree
                    )
        return tokens
