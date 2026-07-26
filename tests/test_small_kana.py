"""小書きカナ(「ハァ」「ウッセェ」など)の吸収のテスト。

単独の小書きカナは単語リストの発音には現れない(単語側は format_kana で正規化済み)
ため、歌詞の読みに残ると一致する単語がなく行全体の候補が0件になる。
「うっせぇわ」のサビが1件も変換できなかったのがこれ。
"""

from __future__ import annotations

from typing import Any

import pytest

from soramimic.kana_to_syllable import KanaToSyllable, absorb_small_kana

# 直前のカナと合わせて1モーラを構成する = 温存される組み合わせ
STICKY = [
    "ウァ", "クィ", "スェ", "ツォ", "ヌァ", "フェ", "ムォ", "ユァ", "ルィ",
    "グェ", "ズォ", "ヅァ", "ブィ", "プェ", "ヴァ",
    "テャ", "ティ", "テュ", "テョ", "デャ", "ディ", "デュ", "デョ",
    "イャ", "キャ", "シュ", "チョ", "ニャ", "ヒュ", "ミョ", "リャ",
    "ギュ", "ジョ", "ヂャ", "ビュ", "ピョ",
    "キェ", "シェ", "チェ", "ニェ", "ヒェ", "ミェ", "リェ", "ギェ", "ジェ",
    "ヂェ", "ビェ", "ピェ",
    "トゥ", "ドゥ",
]  # fmt: skip


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 同母音の引き伸ばし表記 → 大文字
        ("ウッセェワ", "ウッセエワ"),
        ("ハァ", "ハア"),
        ("リィ", "リイ"),
        ("スゥ", "スウ"),
        ("ノォ", "ノオ"),
        # 1モーラを構成する組み合わせ → そのまま
        ("ディズニー", "ディズニー"),
        ("ティラミス", "ティラミス"),
        ("ファイト", "ファイト"),
        ("ウィスキー", "ウィスキー"),
        ("シェフ", "シェフ"),
        ("トゥース", "トゥース"),
        ("キャンプ", "キャンプ"),
        ("ヴァイオリン", "ヴァイオリン"),
        # 単独で現れた小書き → 大文字
        ("ァ", "ア"),
        ("ェェ", "エエ"),
        ("ンョ", "ンヨ"),
        # 連続する小書き(1つ目だけくっつく)
        ("ヴァァ", "ヴァア"),
        ("ファァァ", "ファアア"),
        # ひらがなも同じ規則で、ひらがなのまま直す
        ("うっせぇわ", "うっせえわ"),
        ("はぁ", "はあ"),
        ("しぇふ", "しぇふ"),
        ("ちょきん", "ちょきん"),
        # 促音・長音・小書き以外には触らない
        ("ウッ", "ウッ"),
        ("カーッ", "カーッ"),
        ("カタカナ", "カタカナ"),
        ("", ""),
    ],
)
def test_absorb_small_kana(text: str, expected: str) -> None:
    assert absorb_small_kana(text) == expected
    # 1文字→1文字の置換なので長さが変わらない(位置対応を壊さない)
    assert len(absorb_small_kana(text)) == len(text)


@pytest.mark.parametrize("pair", STICKY)
def test_sticky_pairs_are_single_syllable(pair: str) -> None:
    """温存する組み合わせは split でも1ユニットになること(分かれると単独小書きが残る)。"""
    assert absorb_small_kana(pair) == pair
    assert KanaToSyllable().split(pair) == [pair]


@pytest.mark.parametrize(
    "text", ["ウッセェワ", "ハァ", "リィ", "イェーガー", "クヮ", "ヴァァ", "ェ"]
)
def test_no_lone_small_kana_unit_remains(text: str) -> None:
    units = KanaToSyllable().split(absorb_small_kana(text)) or []
    assert all(u not in "ァィゥェォヮャュョ" or len(u) != 1 for u in units), units


def test_tokenize_absorbs_small_kana(pieces: dict[str, Any]) -> None:
    """トークナイズの入口で吸収され、表層(元歌詞の表記)は変わらないこと。"""
    ta = pieces["text_analyzer"]

    def units(text: str) -> list[str]:
        tokens = ta.tokenize_together([text])[0]
        return [t["pronunciation"] for t in ta.get_yomi_and_phrase_break(tokens)]

    assert units("ウッセェワ") == ["ウッ", "セエ", "ワ"]
    assert units("うっせぇわ") == ["ウッ", "セエ", "ワ"]
    assert units("ハァ") == ["ハア"]
    assert units("シェフ") == ["シェ", "フ"]  # 1モーラの組み合わせはそのまま

    tokens = ta.tokenize_together(["うっせぇわ"])[0]
    assert "".join(t["surface_form"] for t in tokens) == "うっせぇわ"


def test_generate_returns_candidates_for_small_kana_line(pieces: dict[str, Any]) -> None:
    """修正前は候補0件だった行が変換できること。"""
    wl = pieces["word_list"]
    maker = pieces["maker"]
    db = wl.parse_tidy(
        "id,original,surface,pronunciation\n1,ウッセエワ,ウッセエワ,ウッセエワ\n2,ハア,ハア,ハア",
        "",
    )
    results = maker.generate(["ウッセェワ", "ハァ"], db, {})
    assert [w["surface"] for w in results[0]] == ["ウッセエワ"]
    assert [w["surface"] for w in results[1]] == ["ハア"]
