# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Any
from soramimic_python.core.mecab_tokenizer import MeCabTokenizer
from soramimic_python.core.character import Kanji, Character
from soramimic_python.core.kana_to_syllable import KanaToSyllable
from soramimic_python.core.english import English
from soramimic_python.core.text_analyzer import TextAnalyzer
from soramimic_python.core.kana_similarity import KanaSimilarity
from soramimic_python.core.soramimic import SoramimiMaker
from soramimic_python.core.wordlist import WordList


# ====== パス定義（JSの定数をPythonに） ======
data_dir = Path(__file__).resolve().parent.parent / "data"
KANJIDICT_PATH = data_dir / "kanjiyomi.json"
ENGLISH_DICTIONARY_PATH = data_dir / "bep-eng.json"
ROMAN_TREE_PATH = data_dir / "tree_roma2kana.json"

VOWEL_SIMILARITY_PATH = data_dir / "simVowelsSimple.json"
CONSONANT_SIMILARITY_PATH = data_dir / "simConsonantsSimple.json"
KANA2PHONON_PATH = data_dir / "kana2phonon.json"


# ====== ユーティリティ ======
def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

# initialize

_kanji_dict = _load_json(KANJIDICT_PATH)
_english_dictionary = _load_json(ENGLISH_DICTIONARY_PATH)
_roman_tree = _load_json(ROMAN_TREE_PATH)
_vowel_similarity = _load_json(VOWEL_SIMILARITY_PATH)
_consonant_similarity = _load_json(CONSONANT_SIMILARITY_PATH)
_kana2phonon = _load_json(KANA2PHONON_PATH)

_mecab = MeCabTokenizer()
def _tokenize_sentences(texts: list[str]) -> list[list[dict[str, str]]]:
    tokens_list = [_mecab.tokenize(text) for text in texts]
    return tokens_list
get_yomi = _mecab.get_yomi
_kanji = Kanji(_kanji_dict)
_character = Character(_kanji)
_k2s = KanaToSyllable()
_english = English(_english_dictionary, _roman_tree)
_text_analyzer = TextAnalyzer(_character, _k2s, _english, _tokenize_sentences, get_yomi)

# 5) そらみみメーカー等の構築
_kana_similarity = KanaSimilarity(_vowel_similarity, _consonant_similarity, _kana2phonon)
soramimi_maker = SoramimiMaker(_kana_similarity, _text_analyzer)
wordlist = WordList(_text_analyzer)

