"""重複なし生成のstreaming exact検索をJS版と同じ境界条件で固定する。"""

from __future__ import annotations

import math
from typing import Any

import pytest
from helpers import fixed_yomi, single_token_tokenizer

from soramimic import create_soramimic, load_default_data, scale_similarity
from soramimic.maker import _WordlistIndex, normalize_unit_weights

PARAM: dict[str, Any] = {
    "VOWEL_RATIO": 0.8,
    "VARIATION_COST": 16,
    "SAME_PHRASE_BREAK_REWARD": 0,
    "MID_PHRASE_BREAK_PENALTY": 20,
    "WORD_NUMBER_PENALTY": 20,
    "DUPLICATE": False,
}


def _entry(pieces: dict[str, Any], word_id: str, surface: str, kana: str) -> dict[str, Any]:
    return {
        "id": word_id,
        "surface": surface,
        "original": surface,
        "kana": kana,
        "pronunciation": pieces["text_analyzer"].yomi_to_syllable(kana),
        "vcost": 0,
    }


def test_js_tie_order_and_same_id_later_entry_wins(pieces: dict[str, Any]) -> None:
    def entry(word_id: str, surface: str) -> dict[str, Any]:
        return _entry(pieces, word_id, surface, "カ")

    db = {
        1: [
            entry("10", "数値10"),
            entry("z", "非数値先"),
            entry("2", "数値2先"),
            entry("01", "先頭ゼロ"),
            entry("2", "数値2後"),
            entry("a", "非数値後"),
        ]
    }

    results = pieces["maker"].generate(["カ"] * 5, db, PARAM)

    assert [line[0]["id"] for line in results] == ["2", "10", "z", "01", "a"]
    assert results[0][0]["surface"] == "数値2後"


def test_same_id_readings_use_minimum_and_are_excluded_together(pieces: dict[str, Any]) -> None:
    db = {
        1: [
            _entry(pieces, "7", "同IDの悪い読み", "キ"),
            _entry(pieces, "7", "同ID完全一致先", "カ"),
            _entry(pieces, "7", "同ID完全一致後", "カ"),
            _entry(pieces, "8", "別ID完全一致", "カ"),
        ]
    }

    results = pieces["maker"].generate(["カ", "カ"], db, PARAM)

    assert results[0][0]["surface"] == "同ID完全一致後"
    assert results[1][0]["id"] == "8"


def test_used_ids_are_excluded_across_lines(pieces: dict[str, Any]) -> None:
    db = {
        1: [
            _entry(pieces, "2", "第一候補", "カ"),
            _entry(pieces, "10", "第二候補", "カ"),
        ]
    }
    results = pieces["maker"].generate(["カ", "カ"], db, PARAM)
    assert [line[0]["id"] for line in results] == ["2", "10"]


def test_future_lock_and_previous_gap_ids_are_excluded(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    db = {
        1: [
            _entry(pieces, "2", "固定候補", "カ"),
            _entry(pieces, "10", "前gap候補", "カ"),
            _entry(pieces, "11", "後gap候補", "カ"),
        ]
    }
    locked = {
        **_entry(pieces, "2", "固定語", "カ"),
        "sim": 0,
        "score": 0,
        "period": [1, 2],
        "originalkana": "カ",
    }

    result = pieces["maker"].generate_from_tokens(
        ta.tokenize_together(["カカカ"]), db, PARAM, locks_per_line=[[locked]]
    )[0]

    assert [word["id"] for word in result] == ["10", "2", "11"]


def test_filler_coexists_with_streaming_search(pieces: dict[str, Any]) -> None:
    db = {1: [_entry(pieces, "0", "一件だけ", "カ")]}
    result = pieces["maker"].generate(["カカ"], db, PARAM)[0]

    assert sum(not word.get("filler") for word in result) == 1
    assert sum(bool(word.get("filler")) for word in result) == 1
    assert [word["id"] for word in result if not word.get("filler")] == ["0"]


@pytest.mark.parametrize(
    ("weights", "expected"),
    [([1.5, 0.5], "前一致"), ([0.5, 1.5], "後一致")],
)
def test_position_weights(pieces: dict[str, Any], weights: list[float], expected: str) -> None:
    db = {
        2: [
            _entry(pieces, "0", "前一致", "カキ"),
            _entry(pieces, "1", "後一致", "キカ"),
        ]
    }
    tokens = pieces["text_analyzer"].tokenize_together(["カカ"])
    result = pieces["maker"].generate_from_tokens(tokens, db, PARAM, weights_per_line=[weights])
    assert result[0][0]["surface"] == expected


def _monotie_app(vowel_ratio: float):
    data = load_default_data(similarity="monotie")
    return create_soramimic(
        kanji_dict=data["kanji_dict"],
        english_dict=data["english_dict"],
        roman_tree=data["roman_tree"],
        vowel_similarity=scale_similarity(data["vowel_similarity"], 2 * vowel_ratio),
        consonant_similarity=scale_similarity(data["consonant_similarity"], 2 * (1 - vowel_ratio)),
        kana2phonon=data["kana2phonon"],
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
    )


@pytest.mark.parametrize(("ratio", "expected_id"), [(0.2, "1"), (0.5, "0"), (0.8, "0")])
def test_vowel_ratio(ratio: float, expected_id: str) -> None:
    app = _monotie_app(ratio)
    units = app.text_analyzer.yomi_to_syllable
    db = {
        1: [
            {
                "id": "0",
                "surface": "母音一致",
                "original": "母音一致",
                "kana": "サ",
                "pronunciation": units("サ"),
                "vcost": 0,
            },
            {
                "id": "1",
                "surface": "子音一致",
                "original": "子音一致",
                "kana": "キ",
                "pronunciation": units("キ"),
                "vcost": 0,
            },
        ]
    }
    result = app.soramimi_maker.generate(
        ["カ"], db, {**PARAM, "VOWEL_RATIO": ratio, "VARIATION_COST": 20 * ratio}
    )
    assert result[0][0]["id"] == expected_id


@pytest.mark.parametrize("source", ["カンカ", "カッカ", "カーカ"])
def test_n_sokuon_long_vowel_variation_cost(source: str) -> None:
    app = _monotie_app(0.8)
    db = app.word_list.parse_plain("短縮候補,カカ")
    result = app.soramimi_maker.generate([source], db, PARAM)
    assert result[0][0]["surface"] == "短縮候補"
    assert result[0][0]["sim"] == 16


def test_duplicate_true_keeps_shared_cache_and_existing_behavior(
    pieces: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    maker = pieces["maker"]
    db = {
        1: [
            _entry(pieces, "2", "第一候補", "カ"),
            _entry(pieces, "10", "第二候補", "カ"),
        ]
    }
    original = maker._get_similar_word
    calls = 0

    def counted(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(maker, "_get_similar_word", counted)
    result = maker.generate(["カ", "カ"], db, {**PARAM, "DUPLICATE": True})

    assert [line[0]["id"] for line in result] == ["2", "2"]
    assert calls == 1
    assert [word["id"] for word in maker.get_candidates(db, ["カ"], PARAM, 2)] == ["2", "10"]


def test_streaming_result_matches_full_exact_across_chunk_boundary(pieces: dict[str, Any]) -> None:
    """全候補exactから禁止IDを除いた先頭と、bounded streamingの結果が一致する。"""
    maker = pieces["maker"]
    db = {1: [_entry(pieces, str(i), f"候補{i}", "キ" if i < 256 else "カ") for i in range(300)]}
    target = ["カ"]
    kana_dist = pieces["kana_similarity"].get_kana_similarity(PARAM)
    full_index = _WordlistIndex(db, kana_dist)
    streaming_index = _WordlistIndex(db, kana_dist)
    excluded: set[str] = set()

    full = maker._get_similar_word(full_index, target, kana_dist, PARAM["VARIATION_COST"])
    expected = [word for word in full if word["id"] not in excluded][:1]
    actual = maker._get_best_available_word(
        streaming_index, target, kana_dist, excluded, PARAM["VARIATION_COST"]
    )

    assert actual == expected
    assert actual[0]["id"] == "256", "2番目のchunkで見つけたexact最良を採用する"
    assert streaming_index._cache == {}, "streaming経路は全bucket候補索引を構築しない"


def test_streaming_result_matches_full_exact_with_weights_and_variations(
    pieces: dict[str, Any],
) -> None:
    maker = pieces["maker"]
    ta = pieces["text_analyzer"]
    db = pieces["word_list"].parse_plain(
        "候補A,ゴメンネ\n候補B,サンタサン\n候補C,ホッケー\n候補D,ゴネネ\n候補E,サタサ\n候補F,ホケ"
    )
    target = [
        unit["pronunciation"]
        for unit in ta.get_yomi_and_phrase_break(ta.tokenize_together(["ゴメンネ"])[0])
    ]
    weights = normalize_unit_weights(
        [0 if i % 3 == 0 else 1 + i % 2 for i in range(len(target))], len(target)
    )
    kana_dist = pieces["kana_similarity"].get_kana_similarity(PARAM)
    index = _WordlistIndex(db, kana_dist)
    excluded = {"0"}

    full = maker._get_similar_word(index, target, kana_dist, PARAM["VARIATION_COST"], weights)
    expected = [word for word in full if word["id"] not in excluded][:1]
    actual = maker._get_best_available_word(
        index, target, kana_dist, excluded, PARAM["VARIATION_COST"], weights
    )

    assert actual == expected


def test_unknown_pronunciation_stays_infinite_with_zero_weight(pieces: dict[str, Any]) -> None:
    """未知unitに重み0を掛けてもINF*0のnanへ崩さない（_ldと同じINF）。"""
    maker = pieces["maker"]
    db = {
        2: [
            {
                **_entry(pieces, "0", "未知読み", "カカ"),
                "pronunciation": ["未知", "カ"],
            }
        ]
    }
    kana_dist = pieces["kana_similarity"].get_kana_similarity(PARAM)
    result = maker._get_best_available_word(
        _WordlistIndex(db, kana_dist), ["カ", "カ"], kana_dist, set(), unit_weights=[0.0, 2.0]
    )

    assert math.isinf(result[0]["sim"])
