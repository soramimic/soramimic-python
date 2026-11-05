"""All-entry reading providers and their validation boundary."""

from __future__ import annotations

from typing import Any

import pytest
from helpers import fixed_yomi, single_token_tokenizer

from soramimic import create_soramimic, resolve_wordlist_reading
from soramimic.word_list import WordList


def test_provider_receives_explicit_and_missing_readings(default_data: dict[str, Any]) -> None:
    seen: list[str] = []

    def read(text: str) -> str:
        seen.append(text)
        return {"メカX": "メカエックス", "メカ2": "メカニ", "してい": "シテイ"}[text]

    app = create_soramimic(
        **default_data,
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
        wordlist_reading=read,
    )
    db = app.word_list.parse_tidy(
        "id,original,surface,pronunciation\n"
        "1,メカＸ,メカＸ,\n2,別表記,別表記,メカ２\n3,表記,表記,してい",
        max_units=8,
    )
    assert seen == ["メカX", "メカ2", "してい"]
    assert {w["kana"] for bucket in db.values() for w in bucket} == {
        "メカエックス",
        "メカニ",
        "シテイ",
    }


@pytest.mark.parametrize("result", ["メカX", "メカ2", "", "カ ナ"])
def test_provider_failure_reports_original_csv_line(pieces: dict[str, Any], result: str) -> None:
    wl = WordList(pieces["text_analyzer"], reading_resolver=lambda text: result)
    with pytest.raises(ValueError) as exc:
        wl.parse_tidy(
            "id,original,surface,pronunciation,type\n"
            "1,ネコ,ネコ,ネコ,skip\n2,メカＸ,メカＸ,メカＸ,keep",
            "type = keep",
        )
    assert "3行目「メカＸ」" in str(exc.value)
    assert "メカＸ" in str(exc.value)
    assert "カナで指定" in str(exc.value)


def test_plain_error_keeps_source_line_with_comments_and_alternate_readings(
    pieces: dict[str, Any],
) -> None:
    def read(text: str) -> str:
        return "X" if text == "bad" else "ネコ"

    wl = WordList(pieces["text_analyzer"], reading_resolver=read)
    with pytest.raises(ValueError, match="4行目「対象」"):
        wl.parse_plain("# comment\n\nネコ,ネコ,ねこ\n対象,bad")


def test_reading_boundary_normalizes_before_and_after_provider() -> None:
    seen: list[str] = []

    def read(text: str) -> str:
        seen.append(text)
        return "めかｴｯｸｽ"

    assert resolve_wordlist_reading(" メカＸ ", read) == "メカエックス"
    assert seen == ["メカX"]


@pytest.mark.parametrize("style", ["tidy", "plain", "no-column"])
def test_supplied_readings_use_normalizer_only(default_data: dict[str, Any], style: str) -> None:
    inferred: list[str] = []
    supplied: list[str] = []

    def infer(text: str) -> str:
        inferred.append(text)
        return "ワナイ"

    def normalize(text: str) -> str:
        supplied.append(text)
        return "ハナイ"

    app = create_soramimic(
        **default_data,
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
        wordlist_reading=infer,
        wordlist_pronunciation=normalize,
    )
    if style == "tidy":
        db = app.word_list.parse_tidy(
            "id,original,surface,pronunciation\n"
            "1,はない,はない,\n2,はない,はない,はない\n3,はない,はない,NA"
        )
    elif style == "plain":
        db = app.word_list.parse_plain("はない\nはない,はない\nはない,NA")
    else:
        db = app.word_list.parse_tidy("id,original,surface\n1,はない,はない\n2,はない,はない")

    assert inferred == ["はない", "はない"]
    assert supplied == ([] if style == "no-column" else ["はない"])
    assert {word["kana"] for bucket in db.values() for word in bucket} == (
        {"ワナイ"} if style == "no-column" else {"ワナイ", "ハナイ"}
    )


def test_supplied_reading_error_retains_source_context(pieces: dict[str, Any]) -> None:
    def reject(text: str) -> str:
        raise ValueError(f"指定した読み「{text}」をカナで指定してください")

    wl = WordList(pieces["text_analyzer"], pronunciation_normalizer=reject)
    with pytest.raises(ValueError, match="4行目「対象」.*メカX"):
        wl.parse_plain("# comment\n\nネコ\n対象,メカＸ")
