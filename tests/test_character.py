"""character(Kanji / Character / TokenFormatter)の代表ケースのテスト。"""

from __future__ import annotations

from typing import Any

from helpers import make_token

from soramimic.character import Character, Kanji, TokenFormatter


def test_kanji_allocate_and_to_kana(default_data: dict[str, Any]) -> None:
    kanji = Kanji(default_data["kanji_dict"])
    assert kanji.allocate("東京", "トウキョウ") == [["東", "トウ"], ["京", "キョウ"]]
    assert kanji.is_fullmatch("東京") is True
    assert kanji.is_fullmatch("東京タワー") is False
    # to_kana は各文字の先頭読みを連結
    assert kanji.to_kana("東京") == "ヒガシキョウ"


def test_balanced_allocate() -> None:
    # pronunciation が長い: 1文字ずつに surface を複製し in_surface_pos を振る
    out = Character.balanced_allocate("カ", "カア")
    assert out == [
        {"surface_form": "カ", "pronunciation": "カ", "in_surface_pos": 0},
        {"surface_form": "カ", "pronunciation": "ア", "in_surface_pos": 1},
    ]


def test_character_tokenize_char_index(default_data: dict[str, Any]) -> None:
    kanji = Kanji(default_data["kanji_dict"])
    character = Character(kanji)
    tokens = [make_token("ネコ", pronunciation="ネコ")]
    out = character.tokenize(tokens)
    assert [t["surface_form"] for t in out] == ["ネ", "コ"]
    assert [t["pronunciation"] for t in out] == ["ネ", "コ"]
    assert [t["char_index"] for t in out] == [0, 1]
    assert all("subword" in t for t in out)


def test_token_formatter_phrase_and_number() -> None:
    tf = TokenFormatter()
    tokens = [
        make_token("ネコ", pronunciation="ネコ"),
        make_token("3", pronunciation="*"),
    ]
    out = tf.format(tokens)
    # 数字は読みが振られる
    three = next(t for t in out if t["surface_form"] == "3")
    assert three["pronunciation"] == "サン"
    # phrase index が付与される(先頭は0)
    assert out[0]["phrase"] == 0
