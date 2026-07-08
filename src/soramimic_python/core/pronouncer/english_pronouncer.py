import neologdn
from soramimic_python.core.pronouncer.base import BasePronouncer

import pyopenjtalk
from e2k import C2K, NGram
import re

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
    
class EnglishPronouncer(BasePronouncer):

    def get_match_pattern_with_tag(self, tag: str) -> str:
        return fr"(?P<{tag}>(?:[\p{{Latin}}']+))"

    def pronounce(self, text: str) -> str:
        t = neologdn.normalize(text)
        if ngram(t):
            return c2k(t)
        else:
            return ngram.as_is(t)
