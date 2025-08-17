import re
from typing import Any
import neologdn
from e2k import C2K, NGram

c2k = C2K()
ngram = NGram()


class Apostrophe:
    """
    JS Apostrophe() を Python へ移植
    - to_string: ’ と ' をプレースホルダ "APOSTROPHE" に置換
    - to_sign:   プレースホルダを ' に戻す
    - remove_string: プレースホルダを削除
    - include:  プレースホルダを含むか
    - format:   全角風の ’ を ' に正規化
    """

    STRING_APOSTROPHE = "APOSTROPHE"

    def to_string(self, text: str) -> str:
        # JS: text.split("’").join("'").split("'").join(STRING_APOSTROPHY)
        return text.replace("’", "'").replace("'", self.STRING_APOSTROPHE)

    def to_sign(self, text: str) -> str:
        return text.replace(self.STRING_APOSTROPHE, "'")

    def remove_string(self, text: str) -> str:
        return text.replace(self.STRING_APOSTROPHE, "")

    def include(self, text: str) -> bool:
        return self.STRING_APOSTROPHE in text

    def format(self, text: str) -> str:
        # /[’]/g -> "'"
        return re.sub(r"[’]", "'", text)


class English:
    """
    JS English(DICTIONARY, TREE) を Python へ移植
    - DICTIONARY: 英単語→カナ、かつ単文字 A..Z → カナ を含む dict を想定
    - TREE: ローマ字→カナのトライ（ネスト dict; 葉は str カナ）
    - tokenizer: .tokenize(str) -> List[dict(surface_form, pronunciation, ...)]
    """

    def __init__(self):
        self.apostrophe = Apostrophe()

    def _english_to_kana(
        self, text: str
    ) -> str:
        t = neologdn.normalize(text)
        if ngram(t):
            return c2k(t)
        else:
            return ngram.as_is(t)

    def is_fullmatch(self, text: str) -> bool:
        return re.fullmatch(r"[a-zA-Z']+", text) is not None

    def _tokenize(self, text: str, tokenizer) -> list[dict[str, Any]]:
        # 1) アポストロフィを一時トークンに置換してからトークナイズ
        str_val = self.apostrophe.to_string(text)
        tokens = tokenizer.tokenize(str_val)

        # 2) 英単語のみの token は surface を元に戻し、発音が "*" の場合は英語→カナへ
        out = []
        for token in tokens:
            surf = token.get("surface_form", "")
            pron = token.get("pronunciation", "")

            if self.is_fullmatch(surf):
                # APOSTROPHE を ' に戻す
                surf_fixed = self.apostrophe.to_sign(surf)
                token["surface_form"] = surf_fixed

                if pron == "*":
                    token["pronunciation"] = self._english_to_kana(
                        surf_fixed, self.DICTIONARY, self.TREE
                    )
            out.append(token)
        return out

    def to_kana(self, text: str) -> str:
        return self._english_to_kana(text)


if __name__ == "__main__":
    # Example usage
    english_dict = {"HELLO": "ハロー", "WORLD": "ワールド"}
    roman_tree = {
        "h": {"e": {"l": {"l": {"o": "ハロー"}}}},
        "w": {"o": {"r": {"l": {"d": "ワールド"}}}},
    }
    english = English(english_dict, roman_tree)

    text = "Hello World"
    tokens = english._tokenize(text)
    for token in tokens:
        print(token)
