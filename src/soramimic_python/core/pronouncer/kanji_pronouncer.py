import json
from pathlib import Path

from soramimic_python.core.pronouncer.base import BasePronouncer

def load_default_kanjidict() -> dict[str, list[str]]:
    default_kanjidict_path = Path(__file__).parent.parent.parent / "data/kanjiyomi.json"
    with default_kanjidict_path.open(encoding="utf-8") as f:
        kanjidict: dict[str, list[str]] = json.load(f)
        return kanjidict
    
class KanjiPronouncer(BasePronouncer):
    """
    dictionary: dict[str, list[str]]
      各漢字に対応する読み候補（カタカナ）の配列（長い順でソート済みを想定）
    """

    def __init__(self, dictionary: dict[str, list[str]] | None):
        if dictionary is None:
            self.dictionary = load_default_kanjidict()
        else:
            self.dictionary = dictionary

    def get_match_pattern_with_tag(self, tag: str) -> str:
        return fr'(?P<{tag}>(?:\p{{Han}}|ヶ|ヵ)+)'

    def pronounce(self, text: str) -> str:
        kana = []
        for ch in text:
            if ch in self.dictionary:
                kana.append(self.dictionary[ch][0])
        return "".join(kana)