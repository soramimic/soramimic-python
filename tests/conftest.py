"""テスト用の共通フィクスチャ。"""

from __future__ import annotations

from typing import Any

import pytest
from helpers import fixed_yomi, single_token_tokenizer

from soramimic.character import Character, Kanji
from soramimic.english import English
from soramimic.factory import load_default_data
from soramimic.kana_similarity import KanaSimilarity
from soramimic.kana_to_syllable import KanaToSyllable
from soramimic.maker import SoramimiMaker
from soramimic.text_analyzer import TextAnalyzer
from soramimic.word_list import WordList


@pytest.fixture(scope="session")
def default_data() -> dict[str, Any]:
    return load_default_data()


@pytest.fixture(scope="session")
def pieces(default_data: dict[str, Any]) -> dict[str, Any]:
    """個別コンポーネントを fake トークナイザで組み上げて返す。"""
    kanji = Kanji(default_data["kanji_dict"])
    character = Character(kanji)
    k2s = KanaToSyllable()
    english = English(default_data["english_dict"], default_data["roman_tree"])
    text_analyzer = TextAnalyzer(character, k2s, english, single_token_tokenizer, fixed_yomi)
    kana_similarity = KanaSimilarity(
        default_data["vowel_similarity"],
        default_data["consonant_similarity"],
        default_data["kana2phonon"],
    )
    maker = SoramimiMaker(kana_similarity, text_analyzer)
    word_list = WordList(text_analyzer)
    return {
        "kanji": kanji,
        "character": character,
        "k2s": k2s,
        "english": english,
        "text_analyzer": text_analyzer,
        "kana_similarity": kana_similarity,
        "maker": maker,
        "word_list": word_list,
    }
