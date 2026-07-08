"""text_analyzer の代表ケースのテスト。"""

from __future__ import annotations

from typing import Any


def test_format_kana(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    assert ta.format_kana("cat") == "キャット"
    assert ta.format_kana("ネコ") == "ネコ"
    # 全角英字は [a-zA-Z] にマッチせず、removeSign の半角化で "cat" になる
    assert ta.format_kana("ｃａｔ") == "cat"


def test_yomi_to_variation(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    assert ta.yomi_to_variation("カア") == [["カ", "ア"], ["カー"]]
    assert ta.yomi_to_syllable("カード") == ["カー", "ド"]


def test_tokenize_together_and_phrase_break(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    tokens_list = ta.tokenize_together(["ネコカード"])
    gpb = ta.get_yomi_and_phrase_break(tokens_list[0])
    assert [t["pronunciation"] for t in gpb] == ["ネ", "コ", "カー", "ド"]
    # カ+ー が1モーラに統合され、ド は char_index=4 を保持(JS挙動)
    assert [t["char_index"] for t in gpb] == [0, 1, 2, 4]
    assert all("mora" in t and "phrase" in t for t in gpb)


def test_format_tokens_list_english_and_kanji(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    # 単一トークン fake なので "cat" 全体が英単語として読み化される
    tokens_list = ta.format_tokens_list([[_mk("cat")]])
    assert tokens_list[0][0]["pronunciation"] == "キャット"
    # 漢字は kanji.to_kana で補完される
    tokens_list2 = ta.format_tokens_list([[_mk("東京")]])
    assert tokens_list2[0][0]["pronunciation"] == "ヒガシキョウ"


def _mk(surface: str) -> dict[str, Any]:
    from helpers import make_token

    return make_token(surface, pronunciation="*")
