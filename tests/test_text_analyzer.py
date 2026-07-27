"""text_analyzer の代表ケースのテスト。"""

from __future__ import annotations

from typing import Any


def test_format_kana(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    assert ta.format_kana("cat") == "キャット"
    assert ta.format_kana("ネコ") == "ネコ"
    # 全角英字は [a-zA-Z] にマッチせず、removeSign の半角化で "cat" になる
    assert ta.format_kana("ｃａｔ") == "cat"


def test_format_kana_converts_only_matched_english(pieces: dict[str, Any]) -> None:
    """英字の並びは、マッチした部分だけがカナ化される。

    かつては置換コールバックが match ではなく text 全体を to_kana して返していたため、
    英字がk箇所ある文字列の読みがおよそk+1倍に膨張していた(後段のバリエーション展開が
    指数爆発する原因)。
    """
    ta = pieces["text_analyzer"]
    # 日本語混じり: 英字部分だけが置き換わり、周りの文字は保持される
    assert ta.format_kana("メガリザードンX") == "メガリザードンエクス"
    assert ta.format_kana("ポケモンGO") == "ポケモンゴー"
    # 英字が複数箇所
    assert ta.format_kana("AとBとC") == "エイトビートシー"
    assert ta.format_kana("Ma's night monkey") == "マエスナイトモンキー"
    assert (
        ta.format_kana("Red-Throated Rainbow-Skink(アカノドニジトカゲ)")
        == "レッドスローテッドレインボーエスキンケイアカノドニジトカゲ"
    )


def test_format_kana_does_not_inflate_with_multiple_english_runs(pieces: dict[str, Any]) -> None:
    """英字が複数箇所あっても読みが膨張しない。"""
    ta = pieces["text_analyzer"]
    jp = "アカノドニジトカゲ"
    assert ta.format_kana("Red" + jp) == "レッド" + jp
    assert ta.format_kana("Red" + jp + "Blue") == "レッド" + jp + "ブルー"
    assert (
        ta.format_kana("Red" + jp + "Blue" + jp + "Green")
        == "レッド" + jp + "ブルー" + jp + "グリーン"
    )

    # 英字を1箇所ずつ増やしても、増分は追加した語の読み長だけ(全体の再カナ化ではない)
    prev = len(ta.format_kana("A" + jp))
    for k in range(2, 6):
        cur = len(ta.format_kana(jp.join(["A"] * k)))
        assert cur - prev <= len(jp) + 4, f"英字{k}箇所で読みが膨張しないこと"
        prev = cur


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
