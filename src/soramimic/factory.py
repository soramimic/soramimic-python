# 移植元: frontend/src/lib/index.js
"""index.js からの移植。

create_soramimic(...): データとトークナイザを注入して各コンポーネントを組み上げる。
load_default_data(): data/ 同梱の JSON を importlib.resources で読み込む。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from typing import Any

from .character import Character, Kanji
from .english import English
from .kana_similarity import KanaSimilarity
from .kana_to_syllable import KanaToSyllable
from .maker import SoramimiMaker
from .text_analyzer import TextAnalyzer
from .word_list import WordList

Token = dict[str, Any]


@dataclass
class Soramimic:
    """createSoramimic の戻り値相当(textAnalyzer, kanaSimilarity, soramimiMaker, wordList)。"""

    text_analyzer: TextAnalyzer
    kana_similarity: KanaSimilarity
    soramimi_maker: SoramimiMaker
    word_list: WordList


def create_soramimic(
    kanji_dict: dict[str, list[str]],
    english_dict: dict[str, str],
    roman_tree: dict[str, Any],
    vowel_similarity: dict[str, dict[str, float]],
    consonant_similarity: dict[str, dict[str, float]],
    kana2phonon: dict[str, Any],
    tokenize_sentenses: Callable[[list[str]], list[list[Token]]],
    get_yomi: Callable[..., Any],
) -> Soramimic:
    """index.js の createSoramimic 相当。データとトークナイザを注入して組み上げる。"""
    kanji = Kanji(kanji_dict)
    character = Character(kanji)
    k2s = KanaToSyllable()
    english = English(english_dict, roman_tree)
    text_analyzer = TextAnalyzer(character, k2s, english, tokenize_sentenses, get_yomi)
    kana_similarity = KanaSimilarity(vowel_similarity, consonant_similarity, kana2phonon)
    soramimi_maker = SoramimiMaker(kana_similarity, text_analyzer)
    word_list = WordList(text_analyzer)
    return Soramimic(
        text_analyzer=text_analyzer,
        kana_similarity=kana_similarity,
        soramimi_maker=soramimi_maker,
        word_list=word_list,
    )


_DATA_FILES = {
    "kanji_dict": "kanjiyomi.json",
    "english_dict": "english-kana.json",
    "roman_tree": "tree_roma2kana.json",
    "vowel_similarity": "simVowelsSimple.json",
    "consonant_similarity": "simConsonantsSimple.json",
    "kana2phonon": "kana2phonon.json",
}


def load_default_data() -> dict[str, Any]:
    """data/ 同梱の 6 つの JSON を読み込んで dict で返す。

    キーは create_soramimic の引数名に対応する。
    """
    data: dict[str, Any] = {}
    data_pkg = resources.files("soramimic.data")
    for key, filename in _DATA_FILES.items():
        with (data_pkg / filename).open("r", encoding="utf-8") as f:
            data[key] = json.load(f)
    return data
