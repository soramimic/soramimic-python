import jaconv

from soramimic_python.core.pronouncer.base import BasePronouncer

class KanaPronouncer(BasePronouncer):
    def get_match_pattern_with_tag(self, tag: str) -> str:
        return fr'(?P<{tag}>(?:\p{{Katakana_Or_Hiragana}}|ゝ|ゞ|ー)+)'

    def pronounce(self, text: str) -> str:
        return jaconv.kata2hira(text)