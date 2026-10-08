"""Long vowels retain their syllables across tokenizer/subword boundaries."""

from __future__ import annotations

from typing import Any

import pytest
from helpers import fixed_yomi, make_token, single_token_tokenizer

from soramimic import create_soramimic


@pytest.fixture(params=[False, True], ids=["default", "reading-positions"])
def app(request: pytest.FixtureRequest, default_data: dict[str, Any]) -> Any:
    return create_soramimic(
        **default_data,
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
        preserve_reading_positions=request.param,
    )


def tokens(parts: list[str]) -> list[dict[str, Any]]:
    return [dict(make_token(part, pronunciation=part), phrase=i) for i, part in enumerate(parts)]


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (["コ", "ーラ"], ["コー", "ラ"]),
        (["キャ", "ーンディ"], ["キャーン", "ディ"]),
        (["カ", "ーット"], ["カーッ", "ト"]),
        (["コ", "ー", "ヒ", "ー"], ["コー", "ヒー"]),
        (["ン", "ー"], ["ンー"]),
        (["カイ", "ー"], ["カ", "イー"]),
        # Ordinary vowel boundaries remain separate; there is no blanket joining.
        (["コ", "ウラ"], ["コ", "ウ", "ラ"]),
        # A line-leading mark has no preceding syllable and must not be discarded.
        (["ーラ"], ["ー", "ラ"]),
    ],
)
def test_syllables_across_subwords(app: Any, parts: list[str], expected: list[str]) -> None:
    units = app.text_analyzer.get_yomi_and_phrase_break(tokens(parts))
    assert [u["pronunciation"] for u in units] == expected
    assert "".join(u["surface_form"] for u in units) == "".join(parts)
    assert "".join(u["pronunciation"] for u in units) == "".join(parts)


def test_cross_subword_long_vowel_keeps_positions(app: Any) -> None:
    units = app.text_analyzer.get_yomi_and_phrase_break(tokens(["ネコ", "ーラ"]))
    assert [u["pronunciation"] for u in units] == ["ネ", "コー", "ラ"]
    assert [u["char_index"] for u in units] == [0, 1, 3]
    assert [u["token_index"] for u in units] == [0, 0, 1]
    assert [u["phrase"] for u in units] == [0, 0, 1]


@pytest.mark.parametrize("duplicate", [False, True])
def test_cross_token_long_vowel_can_select_a_real_word(app: Any, duplicate: bool) -> None:
    db = app.word_list.parse_tidy("id,original,surface,pronunciation\n1,コーラ,コーラ,コーラ", "")
    prepared = app.text_analyzer.format_tokens_list([tokens(["コ", "ーラ"])])
    words = app.soramimi_maker.generate_from_tokens(prepared, db, {"DUPLICATE": duplicate})[0]
    assert len(words) == 1
    assert words[0]["surface"] == "コーラ"
    assert words[0]["period"] == [0, 2]
    assert words[0]["original_surface"] == "コーラ"
    assert not words[0].get("filler")
