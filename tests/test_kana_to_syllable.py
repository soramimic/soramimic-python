"""kana_to_syllable の分割・バリエーション生成のテスト。"""

from __future__ import annotations

from soramimic.kana_to_syllable import (
    KanaToSyllable,
    char_to_consonant,
    char_to_vowel,
    remove_unnatural_kana_pattern,
)


def test_split_basic() -> None:
    k2s = KanaToSyllable()
    assert k2s.split("カード") == ["カー", "ド"]
    assert k2s.split("カア") == ["カア"]
    assert k2s.split("トウキョウ") == ["トウ", "キョウ"]
    assert k2s.split("ファイト") == ["ファ", "イ", "ト"]
    assert k2s.split("コンピューター") == ["コン", "ピュー", "ター"]


def test_split_no_match_returns_none() -> None:
    k2s = KanaToSyllable()
    assert k2s.split("") is None


def test_variation_vowel_ending() -> None:
    k2s = KanaToSyllable()
    # カア → 母音で終わる: [カ,ア] と 長音化 [カー]
    assert k2s.get_variation(k2s.split("カア")) == [["カ", "ア"], ["カー"]]


def test_variation_n_and_sokuon() -> None:
    k2s = KanaToSyllable()
    # ン は [ン] と [""](空は除外され [ン] のみ残る)
    assert k2s.get_variation(["ン"]) == [["ン"]]
    # ッ 同様
    assert k2s.get_variation(["ッ"]) == [["ッ"]]


def test_variation_word() -> None:
    k2s = KanaToSyllable()
    assert k2s.get_variation(k2s.split("カード")) == [["カー", "ド"]]


def test_is_fullmatch() -> None:
    k2s = KanaToSyllable()
    assert k2s.is_fullmatch("キャ") is True
    assert k2s.is_fullmatch("カー") is True
    assert k2s.is_fullmatch("カン") is True
    assert k2s.is_fullmatch("トウ") is True
    # 2モーラ以上は full match しない
    assert k2s.is_fullmatch("カカ") is False


def test_remove_unnatural_kana_pattern() -> None:
    assert remove_unnatural_kana_pattern("アーーー") == "アー"
    assert remove_unnatural_kana_pattern("カァ") == "カー"


def test_char_to_vowel_and_consonant() -> None:
    assert char_to_vowel("カ") == "ア"
    assert char_to_vowel("キ") == "イ"
    assert char_to_vowel("ー") == "ー"
    assert char_to_vowel("ン") == "sp"
    assert char_to_consonant("カ") == "k"
    # sp キーが上書きされ アイウエオ は子音無し("")
    assert char_to_consonant("ア") == ""
    assert char_to_consonant("ン") == "sp"
