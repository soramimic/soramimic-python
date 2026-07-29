"""ルビ記法(｜表層《よみ》)のテスト。

パーサ単体(parse_ruby)と、トークナイズ入口(tokenize_together)での読み上書きを検証する。
ケースは本家JSの tests/ruby.mjs と同一。
"""

from __future__ import annotations

from typing import Any

import pytest

from soramimic import has_ruby, parse_ruby

# (入力, 期待plain, 期待annotations)
PARSE_CASES: list[tuple[str, str, list[dict[str, Any]]]] = [
    # --- 記法なし(素通し) ---
    ("夢は今もめぐりて 忘れがたきふるさと", "夢は今もめぐりて 忘れがたきふるさと", []),
    ("", "", []),
    # --- 基本形 ---
    (
        "｜邪悪《ダークネス》を飼い慣らせ",
        "邪悪を飼い慣らせ",
        [{"start": 0, "end": 2, "reading": "ダークネス"}],
    ),
    # 開始記号は半角 | も受理する
    (
        "|邪悪《ダークネス》を飼い慣らせ",
        "邪悪を飼い慣らせ",
        [{"start": 0, "end": 2, "reading": "ダークネス"}],
    ),
    # 読みのひらがなはカタカナに正規化する(それ以外はそのまま)
    ("｜本気《まじ》", "本気", [{"start": 0, "end": 2, "reading": "マジ"}]),
    ("｜本気《マジ》", "本気", [{"start": 0, "end": 2, "reading": "マジ"}]),
    ("｜延《の》ーばす", "延ーばす", [{"start": 0, "end": 1, "reading": "ノ"}]),
    # 行の途中・末尾
    ("俺の｜心《ハート》", "俺の心", [{"start": 2, "end": 3, "reading": "ハート"}]),
    # 複数ルビ
    (
        "｜本気《マジ》で｜書く《かく》ぜ",
        "本気で書くぜ",
        [{"start": 0, "end": 2, "reading": "マジ"}, {"start": 3, "end": 5, "reading": "カク"}],
    ),
    # 隣接ルビ
    (
        "｜A《エー》｜B《ビー》",
        "AB",
        [{"start": 0, "end": 1, "reading": "エー"}, {"start": 1, "end": 2, "reading": "ビー"}],
    ),
    # --- エスケープ ---
    # \｜ は文字そのもの(記法として解釈しない)
    ("\\｜邪悪《ダークネス》", "｜邪悪《ダークネス》", []),
    ("\\|邪悪《ダークネス》", "|邪悪《ダークネス》", []),
    # 表層・読みの中でもエスケープが効く
    ("｜a\\｜b《ヨミ》", "a｜b", [{"start": 0, "end": 3, "reading": "ヨミ"}]),
    ("｜表層《よ\\《み》", "表層", [{"start": 0, "end": 2, "reading": "ヨ《ミ"}]),
    ("｜表層《よ\\》み》", "表層", [{"start": 0, "end": 2, "reading": "ヨ》ミ"}]),
    # \\ はバックスラッシュ1文字、それ以外の前の \ はそのまま文字
    ("a\\\\b", "a\\b", []),
    ("a\\b", "a\\b", []),
    ("末尾は\\", "末尾は\\", []),
    ("\\\\｜邪悪《ダーク》", "\\邪悪", [{"start": 1, "end": 3, "reading": "ダーク"}]),
    # --- 寛容規則 ---
    # 《よみ》が続かない ｜ は通常文字
    ("｜ふつうの文字", "｜ふつうの文字", []),
    ("｜邪悪だ", "｜邪悪だ", []),
    # 表層は「｜から《まで」なので空白も含む(改行以外の終端は無い)
    ("｜邪悪 《ダークネス》", "邪悪 ", [{"start": 0, "end": 3, "reading": "ダークネス"}]),
    # ｜を伴わない 《…》 は通常文字(暗黙形は未対応)
    ("邪悪《ダークネス》", "邪悪《ダークネス》", []),
    ("《ダークネス》", "《ダークネス》", []),
    # 読みが空 / 表層が空は無効
    ("｜表層《》", "｜表層《》", []),
    ("｜《ヨミ》", "｜《ヨミ》", []),
    # ネスト不可: 後ろの ｜ が勝ち、前の ｜ は通常文字
    ("｜a｜b《ヨミ》", "｜ab", [{"start": 2, "end": 3, "reading": "ヨミ"}]),
    # 改行をまたぐ記法は無効
    ("｜邪悪\n《ダークネス》", "｜邪悪\n《ダークネス》", []),
    ("｜邪悪《ダーク\nネス》", "｜邪悪《ダーク\nネス》", []),
    # 閉じ括弧が無い / 括弧の入れ子
    ("｜邪悪《ダークネス", "｜邪悪《ダークネス", []),
    ("｜a《b《ヨミ》", "｜a《b《ヨミ》", []),
    # --- オフセットはコードポイント単位(JS側のUTF-16 code unitと混同しないこと) ---
    ("𩸽｜邪悪《ダーク》", "𩸽邪悪", [{"start": 1, "end": 3, "reading": "ダーク"}]),
    ("｜𩸽《ホッケ》を焼く", "𩸽を焼く", [{"start": 0, "end": 1, "reading": "ホッケ"}]),
]


@pytest.mark.parametrize(("text", "plain", "annotations"), PARSE_CASES)
def test_parse_ruby(text: str, plain: str, annotations: list[dict[str, Any]]) -> None:
    got = parse_ruby(text)
    assert got["plain"] == plain
    assert got["annotations"] == annotations


def test_has_ruby() -> None:
    assert has_ruby("｜本気《マジ》") is True
    assert has_ruby("本気《マジ》") is False


# --- トークナイズ入口での読み上書き ---
# conftest の pieces は「1行=1トークン(pronunciation='*')」の fake トークナイザなので、
# 注釈区間の分割・強制トークンの挿入・後段の上書き防止だけを見る


def _tokenize(pieces: dict[str, Any], texts: list[str]) -> list[list[dict[str, Any]]]:
    return pieces["text_analyzer"].tokenize_together(texts)


def test_split_by_ruby_is_identity_without_notation(pieces: dict[str, Any]) -> None:
    """記法を含まない行は行全体が1チャンクになり、従来と同じ入力がトークナイザに渡る。"""
    texts = ["夢は今もめぐりて", "ぴえんー", ""]
    chunks, plan = pieces["text_analyzer"].split_by_ruby(texts)
    assert chunks == texts
    assert plan == [[{"type": "chunk", "index": i}] for i in range(len(texts))]


def test_split_by_ruby_splits_at_annotation_boundary(pieces: dict[str, Any]) -> None:
    chunks, plan = pieces["text_analyzer"].split_by_ruby(["｜本気《マジ》で｜書く《かく》ぜ"])
    assert chunks == ["で", "ぜ"]
    assert plan == [
        [
            {"type": "ruby", "surface": "本気", "reading": "マジ"},
            {"type": "chunk", "index": 0},
            {"type": "ruby", "surface": "書く", "reading": "カク"},
            {"type": "chunk", "index": 1},
        ]
    ]


def test_forced_token(pieces: dict[str, Any]) -> None:
    (tokens,) = _tokenize(pieces, ["｜邪悪《ダークネス》"])
    ruby = [t for t in tokens if t.get("ruby")]
    assert len(ruby) == 1
    assert ruby[0]["surface_form"] == "邪悪"
    assert ruby[0]["pronunciation"] == "ダークネス"
    assert ruby[0]["reading"] == "ダークネス"
    assert ruby[0]["pos"] == "名詞"


@pytest.mark.parametrize(
    ("text", "surface", "reading"),
    [
        # かな表層(_set_kana_pronunciation に上書きされない)
        ("｜すもも《ピーチ》", "すもも", "ピーチ"),
        # 英字表層(english.to_kana に上書きされない)
        ("｜love《アイ》", "love", "アイ"),
        # 数字表層(_set_number_pronunciation に上書きされない)
        ("｜1《ワン》", "1", "ワン"),
        # 直後の小書きカナが結合されない
        ("｜あ《ハート》っ", "あ", "ハート"),
        # 直後の長音が結合されない
        ("｜延《の》ー", "延", "ノ"),
    ],
)
def test_reading_is_not_overwritten(
    pieces: dict[str, Any], text: str, surface: str, reading: str
) -> None:
    (tokens,) = _tokenize(pieces, [text])
    ruby = [t for t in tokens if t.get("ruby")]
    assert len(ruby) == 1
    assert ruby[0]["surface_form"] == surface
    assert ruby[0]["pronunciation"] == reading


def test_word_position_recalculated(pieces: dict[str, Any]) -> None:
    """記法を含む行の word_position は結合後に1始まりで振り直される(コードポイント単位)。"""
    (tokens,) = _tokenize(pieces, ["𩸽｜邪悪《ダーク》を食う"])
    expected = []
    pos = 1
    for t in tokens:
        expected.append(pos)
        pos += len(t["surface_form"])
    assert [t["word_position"] for t in tokens] == expected


def test_lines_are_preserved(pieces: dict[str, Any]) -> None:
    """記法あり/なし/空行が混在しても行の対応が崩れない。"""
    tokens_list = _tokenize(pieces, ["普通の行", "｜本気《マジ》で", "", "また普通"])
    assert len(tokens_list) == 4
    assert [t for t in tokens_list[0] if t.get("ruby")] == []
    assert len([t for t in tokens_list[1] if t.get("ruby")]) == 1
    # 空行もチャンクとしてそのままトークナイザに渡る(=fakeの出力がそのまま出る)
    assert "".join(t["surface_form"] for t in tokens_list[2]) == ""
    assert [t for t in tokens_list[3] if t.get("ruby")] == []
