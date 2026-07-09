"""同梱サンプル単語リストのテスト。"""

from __future__ import annotations

import pytest

from soramimic import SAMPLE_WORDLISTS, create_soramimic, load_default_data, load_sample_wordlist


@pytest.fixture(scope="module")
def app():
    def identity_yomi(text):
        return list(text) if isinstance(text, list) else text

    def no_tokenize(_texts):
        raise AssertionError("tokenize should not be called")

    return create_soramimic(
        **load_default_data(),
        tokenize_sentenses=no_tokenize,
        get_yomi=identity_yomi,
    )


def test_unknown_name():
    with pytest.raises(ValueError):
        load_sample_wordlist("pokemon")


@pytest.mark.parametrize("name", SAMPLE_WORDLISTS)
def test_load_and_parse(name, app):
    """全サンプルが読み込め、parse_tidy でDB化できること。"""
    csv_text = load_sample_wordlist(name)
    lines = csv_text.splitlines()
    assert lines[0].startswith("id,original,surface")
    db = app.word_list.parse_tidy(csv_text, "")
    assert db, name
    total = sum(len(v) for v in db.values())
    assert total > len(lines) * 0.5, name  # 大半の行がDB化されている
