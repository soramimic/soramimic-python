"""factory(load_default_data / create_soramimic)のテスト。"""

from __future__ import annotations

from helpers import fixed_yomi, single_token_tokenizer

from soramimic import Soramimic, create_soramimic, load_default_data


def test_load_default_data() -> None:
    data = load_default_data()
    assert set(data.keys()) == {
        "kanji_dict",
        "english_dict",
        "roman_tree",
        "vowel_similarity",
        "consonant_similarity",
        "kana2phonon",
    }
    assert len(data["kanji_dict"]) > 0
    assert len(data["kana2phonon"]) > 0


def test_create_soramimic_builds() -> None:
    data = load_default_data()
    s = create_soramimic(
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
        **data,
    )
    assert isinstance(s, Soramimic)
    assert s.text_analyzer is not None
    assert s.kana_similarity is not None
    assert s.soramimi_maker is not None
    assert s.word_list is not None


def test_create_soramimic_end_to_end() -> None:
    data = load_default_data()
    s = create_soramimic(
        tokenize_sentenses=single_token_tokenizer,
        get_yomi=fixed_yomi,
        **data,
    )
    csv = "id,original,surface,pronunciation\n1,ネコ,ネコ,ネコ\n2,カード,カード,カード"
    db = s.word_list.parse_tidy(csv, "")
    tokens_list = s.text_analyzer.tokenize_together(["ネコ"])
    results = s.soramimi_maker.generate_from_tokens(tokens_list, db, {})
    assert results[0][0]["surface"] == "ネコ"
