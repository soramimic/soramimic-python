"""ゴールデンテスト: 本体JS(main)の実行結果とPython移植の出力一致を検証する。

フィクスチャは tools/generate_golden.mjs で本体JSライブラリを直接実行して生成したもの。
読み推定(kuromoji/MeCab)は使わず、読み固定の入力のみなので、トークナイザ差に
依存しないアルゴリズム部分の互換性を検証している。
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest

from soramimic import create_soramimic, load_default_data

GOLDEN_DIR = Path(__file__).parent / "golden"

# generate_golden.mjs の fakeGetYomi と同じ固定読みテーブル
FAKE_YOMI_TABLE = {
    "東京": "トーキョー",
    "山手": "ヤマノテ",
    "秋葉原": "アキハバラ",
}


def fake_get_yomi(text: Any) -> Any:
    if isinstance(text, list):
        return [FAKE_YOMI_TABLE.get(t, t) for t in text]
    return FAKE_YOMI_TABLE.get(text, text)


def fake_tokenize(_texts: Any) -> Any:
    raise AssertionError("tokenize should not be called in golden tests")


@pytest.fixture(scope="module")
def app():
    data = load_default_data()
    return create_soramimic(
        kanji_dict=data["kanji_dict"],
        english_dict=data["english_dict"],
        roman_tree=data["roman_tree"],
        vowel_similarity=data["vowel_similarity"],
        consonant_similarity=data["consonant_similarity"],
        kana2phonon=data["kana2phonon"],
        tokenize_sentenses=fake_tokenize,
        get_yomi=fake_get_yomi,
    )


def load(name: str) -> Any:
    with open(GOLDEN_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def normalize(obj: Any) -> Any:
    """Python出力をJSON経由の表現に正規化して比較する(intキー→strキー等)。

    JSON.stringify は Infinity を null にするため、こちらも同じ変換を通す。
    """
    return json.loads(
        json.dumps(obj, ensure_ascii=False, default=lambda v: None if v == math.inf else v)
    )


def test_kana_to_syllable(app):
    for case in load("kana_to_syllable.json"):
        assert normalize(app.text_analyzer.yomi_to_syllable(case["input"])) == case["syllables"], (
            case["input"]
        )
        assert (
            normalize(app.text_analyzer.yomi_to_variation(case["input"])) == case["variations"]
        ), case["input"]


def test_format_kana(app):
    for case in load("format_kana.json"):
        assert app.text_analyzer.format_kana(case["input"]) == case["output"], case["input"]


def test_format_tokens_list(app):
    fixture = load("format_tokens_list.json")
    output = app.text_analyzer.format_tokens_list(copy.deepcopy(fixture["input"]))
    assert normalize(output) == fixture["output"]


def test_yomi_and_phrase_break(app):
    fixture = load("yomi_and_phrase_break.json")
    output = [
        app.text_analyzer.get_yomi_and_phrase_break(copy.deepcopy(tokens))
        for tokens in fixture["input"]
    ]
    assert normalize(output) == fixture["output"]


def test_wordlist_plain(app):
    fixture = load("wordlist_plain.json")
    db = app.word_list.parse_plain(fixture["input"])
    assert normalize(db) == fixture["output"]


@pytest.mark.parametrize(
    "name",
    [
        "wordlist_tidy_all.json",
        "wordlist_tidy_category_food.json",
        "wordlist_tidy_category_food_or_category_gadget.json",
        "wordlist_tidy_category_station.json",
        "wordlist_tidy_no_pronunciation.json",
    ],
)
def test_wordlist_tidy(app, name):
    fixture = load(name)
    db = app.word_list.parse_tidy(fixture["input"], fixture["where"])
    assert normalize(db) == fixture["output"]


def test_kana_similarity_samples(app):
    fixture = load("kana_similarity_samples.json")
    kana_dist = app.kana_similarity.get_kana_similarity(fixture["parameter"])
    for a, b, expected in fixture["samples"]:
        assert kana_dist[a][b] == expected, (a, b)


def test_generate_from_tokens(app):
    fixture = load("generate_from_tokens.json")
    db = app.word_list.parse_tidy(fixture["wordlist_csv"], "")
    for case in fixture["cases"]:
        results = app.soramimi_maker.generate_from_tokens(
            copy.deepcopy(case["tokens_list"]),
            copy.deepcopy(db),
            case["parameter"],
        )
        assert normalize(results) == case["results"], case["name"]


def test_get_candidates(app):
    fixture = load("get_candidates.json")
    db = app.word_list.parse_tidy(fixture["wordlist_csv"], "")
    for case in fixture["cases"]:
        output = app.soramimi_maker.get_candidates(copy.deepcopy(db), case["target"], {}, 5)
        assert normalize(output) == case["output"], case["target"]
