from __future__ import annotations

from typing import Any

import pytest
from helpers import fixed_yomi, single_token_tokenizer

from soramimic import create_soramimic, normalize_kana_reading


@pytest.fixture
def position_app(default_data: dict[str, Any]) -> Any:
    return create_soramimic(
        **default_data,
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
        preserve_reading_positions=True,
    )


@pytest.mark.parametrize(
    ("reading", "expected"),
    [
        ("イェカイェ", "イエカイエ"),
        ("クヮカクヮ", "クワカクワ"),
        ("カャカカャ", "カヤカカヤ"),
        ("ァカュ", "アカユ"),
        ("ティファウィシェ", "ティファウィシェ"),
        ("セェ", "セエ"),
        ("ドーーー", "ドーオオ"),
        ("ヲーー", "ヲーオ"),
        ("カッッ", "カッッ"),
        ("んーー", "ンーー"),
    ],
)
def test_source_and_dictionary_share_position_preserving_reading(
    position_app: Any, reading: str, expected: str
) -> None:
    assert normalize_kana_reading(reading) == expected
    assert normalize_kana_reading(expected) == expected
    assert len(expected) == len(reading)
    analyzer = position_app.text_analyzer
    tokens = analyzer.tokenize_together([reading])[0]
    units = analyzer.get_yomi_and_phrase_break(tokens)
    assert "".join(unit["pronunciation"] for unit in units) == expected
    assert "".join(token["surface_form"] for token in tokens) == reading
    assert analyzer.format_kana(reading) == expected
    db = position_app.word_list.parse_tidy(
        f"id,original,surface,pronunciation\n1,表記,表記,{reading}", ""
    )
    assert {word["kana"] for words in db.values() for word in words} == {expected}


@pytest.mark.parametrize(
    ("surfaces", "expected"),
    [(["シ", "ェ", "ー", "ー"], "シェーエ"), (["シ", "ェ", "ァ"], "シェア")],
)
def test_shared_reading_normalizes_across_token_boundaries(
    position_app: Any, surfaces: list[str], expected: str
) -> None:
    from helpers import make_token

    analyzer = position_app.text_analyzer
    tokens = analyzer.format_tokens_list([[make_token(surface) for surface in surfaces]])[0]
    assert "".join(token["pronunciation"] for token in tokens) == expected
    assert "".join(token["surface_form"] for token in tokens) == "".join(surfaces)


def test_mecab_keeps_supplied_kana_reading(default_data: dict[str, Any]) -> None:
    from soramimic.tokenizers.mecab import MeCabTokenizer

    tokenizer = MeCabTokenizer()
    app = create_soramimic(
        **default_data,
        tokenize_sentenses=tokenizer.tokenize,  # type: ignore[arg-type]
        get_yomi=tokenizer.get_yomi,
        preserve_reading_positions=True,
    )
    reading = "オウサマエイガハヘヲイェシェーードーー"
    tokens = app.text_analyzer.tokenize_together([reading])[0]
    units = app.text_analyzer.get_yomi_and_phrase_break(tokens)
    assert "".join(unit["pronunciation"] for unit in units) == normalize_kana_reading(reading)
    assert "".join(unit["surface_form"] for unit in units) == reading


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("reading", ["イェ", "クヮ", "カャ", "カュ"])
def test_word_boundaries_prevent_splitting_one_owned_span(
    position_app: Any, duplicate: bool, reading: str
) -> None:
    kana = normalize_kana_reading(reading)
    db = position_app.word_list.parse_tidy(
        "id,original,surface,pronunciation\n"
        f"1,前,前,{kana[0]}\n2,後,後,{kana[1]}\n3,全,全,{reading}",
        "",
    )
    maker = position_app.soramimi_maker
    params = {"DUPLICATE": duplicate, "WORD_NUMBER_PENALTY": -100}
    split = maker.generate([reading], db, params)[0]
    assert [word["period"] for word in split] == [[0, 1], [1, 2]]
    atomic = maker.generate([reading], db, params, word_boundaries_per_line=[[0, 2]])[0]
    assert [(word["surface"], word["period"]) for word in atomic] == [("全", [0, 2])]
    assert not atomic[0].get("filler")


def test_filler_respects_protected_span(position_app: Any) -> None:
    words = position_app.soramimi_maker.generate(
        ["イェカ"], {}, {}, word_boundaries_per_line=[[0, 2, 3]]
    )[0]
    assert [(word["kana"], word["period"]) for word in words] == [("イエ", [0, 2]), ("カ", [2, 3])]
    assert all(word["filler"] for word in words)
    assert "".join(word["original_surface"] for word in words) == "イェカ"


@pytest.mark.parametrize("boundaries", [[], [1, 2], [0, 1], [0, 2, 1, 2], [0, True, 2]])
def test_invalid_word_boundaries_fail(position_app: Any, boundaries: list[int]) -> None:
    with pytest.raises(ValueError, match="invalid word boundaries"):
        position_app.soramimi_maker.generate(
            ["イェ"], {}, {}, word_boundaries_per_line=[boundaries]
        )


def test_word_boundary_line_count_is_validated(position_app: Any) -> None:
    with pytest.raises(ValueError, match="one entry per line"):
        position_app.soramimi_maker.generate(["イェ"], {}, {}, word_boundaries_per_line=[])


def test_locked_word_cannot_split_protected_span(position_app: Any) -> None:
    tokens = position_app.text_analyzer.tokenize_together(["イェ"])
    with pytest.raises(ValueError, match="locked word splits"):
        position_app.soramimi_maker.generate_from_tokens(
            tokens,
            {},
            {},
            locks_per_line=[[{"period": [0, 1]}]],
            word_boundaries_per_line=[[0, 2]],
        )


def test_all_word_boundaries_preserve_legacy_result(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = pieces["word_list"].parse_tidy("id,original,surface,pronunciation\n1,ネコ,ネコ,ネコ", "")
    expected = maker.generate(["ネコ"], db, {})
    assert maker.generate(["ネコ"], db, {}, word_boundaries_per_line=[[0, 1, 2]]) == expected


def test_empty_line_accepts_its_only_boundary(position_app: Any) -> None:
    assert position_app.soramimi_maker.generate_from_tokens(
        [[]], {}, {}, word_boundaries_per_line=[[0]]
    ) == [[]]
