"""word_list の parse_plain / parse_tidy(where フィルタ含む)テスト。"""

from __future__ import annotations

from typing import Any

from soramimic.word_list import Parser


def _ids(bucket: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(w["surface"], w["id"]) for w in bucket]


def test_parse_tidy_basic(pieces: dict[str, Any]) -> None:
    wl = pieces["word_list"]
    csv = (
        "id,original,surface,pronunciation\n"
        "1,ネコ,ネコ,ネコ\n"
        "2,イヌ,イヌ,イヌ\n"
        "3,カード,カード,カード"
    )
    db = wl.parse_tidy(csv, "")
    # 長さ2バケットに ネコ/イヌ/カード(カード は カー,ド の2ユニット)
    assert 2 in db
    surfaces = {w["surface"] for w in db[2]}
    assert {"ネコ", "イヌ", "カード"} <= surfaces
    neko = next(w for w in db[2] if w["surface"] == "ネコ")
    assert neko["pronunciation"] == ["ネ", "コ"]
    assert neko["id"] == "1"


def test_parse_tidy_where(pieces: dict[str, Any]) -> None:
    wl = pieces["word_list"]
    csv = (
        "id,original,surface,pronunciation,pos\n"
        "1,ネコ,ネコ,ネコ,animal\n"
        "2,イヌ,イヌ,イヌ,animal\n"
        "3,カード,カード,カード,object"
    )
    db = wl.parse_tidy(csv, "pos = animal")
    assert list(db.keys()) == [2]
    assert _ids(db[2]) == [("ネコ", "1"), ("イヌ", "2")]

    db2 = wl.parse_tidy(csv, "pos != animal")
    assert _ids(db2[2]) == [("カード", "3")]

    db3 = wl.parse_tidy(csv, "pos = animal and id != 1")
    assert _ids(db3[2]) == [("イヌ", "2")]


def test_parse_plain(pieces: dict[str, Any]) -> None:
    wl = pieces["word_list"]
    plain = "ネコ\nイヌ,ワンコ,ドッグ\n#コメント行\nカード # 行内コメント\nタイヨウ,タイヨー"
    db = wl.parse_plain(plain)
    # id は「有効行のインデックス」。ネコ=0, イヌ=1, カード=2, タイヨウ=3
    b2 = _ids(db[2])
    assert ("ネコ", "0") in b2
    assert ("ワンコ", "1") in b2  # イヌ行の異表記、original=イヌ
    assert ("カード", "2") in b2
    wanko = next(w for w in db[2] if w["surface"] == "ワンコ")
    assert wanko["original"] == "イヌ"
    assert wanko["pronunciation"] == ["ワー", "コ"]
    # 行内コメントとゼロ幅スペースが除去される
    assert all("#" not in w["surface"] for bucket in db.values() for w in bucket)


def test_parser_eval() -> None:
    p = Parser()
    assert p.eval("pos = 名詞", {"pos": "名詞"}) is True
    assert p.eval("pos = 名詞", {"pos": "動詞"}) is False
    assert p.eval("pos != 動詞", {"pos": "名詞"}) is True
    assert p.eval("pos = 名詞 and x = 1", {"pos": "名詞", "x": "1"}) is True
    assert p.eval("pos = 名詞 and x = 1", {"pos": "名詞", "x": "2"}) is False
    assert p.eval("(a = 1 or b = 2) and c = 3", {"a": "9", "b": "2", "c": "3"}) is True
    # 不正な式は -1
    assert p.eval("pos", {"pos": "名詞"}) == -1


def test_parser_filter_unknown_key_returns_false() -> None:
    p = Parser()
    header = ["id", "surface"]
    df = [["1", "ネコ"]]
    assert p.filter("pos = animal", header, df) is False


def test_parser_eval_contains() -> None:
    p = Parser()
    # スラッシュ区切りの複数値セルに対する部分一致
    assert p.eval("field ~= 物理", {"field": "物理/数学"}) is True
    assert p.eval("field ~= 数学", {"field": "物理/数学"}) is True
    assert p.eval("field ~= 化学", {"field": "物理/数学"}) is False
    # 演算子の間にスペースが無くてもトークナイズできる(field~=物理 形式)
    assert p.eval("field~=物理", {"field": "物理/数学"}) is True
    # 否定
    assert p.eval("field !~= 化学", {"field": "物理/数学"}) is True
    assert p.eval("field !~= 物理", {"field": "物理/数学"}) is False
    # 値が存在しない(undefined)場合は空文字扱い
    assert p.eval("field ~= 物理", {"other": "x"}) is False
    assert p.eval("field !~= 物理", {"other": "x"}) is True
    # 既存 =/!= や and/or/括弧 との組み合わせ
    obj = {"field": "物理/数学", "era": "近代"}
    assert p.eval("field ~= 物理 and era = 近代", obj) is True
    assert p.eval("field ~= 物理 and era = 現代", obj) is False
    assert p.eval("(field ~= 化学 or field ~= 数学) and era != 現代", obj) is True


def test_parse_tidy_where_contains(pieces: dict[str, Any]) -> None:
    wl = pieces["word_list"]
    csv = (
        "id,original,surface,pronunciation,field\n"
        "1,ニュートン,ニュートン,ニュートン,物理/数学\n"
        "2,ガウス,ガウス,ガウス,数学\n"
        "3,ラボアジエ,ラボアジエ,ラボアジエ,化学"
    )
    # field~=物理 形式(スペースなし)。物理を含むのはニュートンのみ
    db = wl.parse_tidy(csv, "field~=物理")
    surfaces = {w["surface"] for bucket in db.values() for w in bucket}
    assert surfaces == {"ニュートン"}

    # 数学を含むのは ニュートン(物理/数学) と ガウス
    db2 = wl.parse_tidy(csv, "field ~= 数学")
    surfaces2 = {w["surface"] for bucket in db2.values() for w in bucket}
    assert surfaces2 == {"ニュートン", "ガウス"}

    # 否定: 数学を含まないのは ラボアジエ のみ
    db3 = wl.parse_tidy(csv, "field !~= 数学")
    surfaces3 = {w["surface"] for bucket in db3.values() for w in bucket}
    assert surfaces3 == {"ラボアジエ"}

    # =/!= との組み合わせ
    db4 = wl.parse_tidy(csv, "field ~= 数学 and id != 1")
    surfaces4 = {w["surface"] for bucket in db4.values() for w in bucket}
    assert surfaces4 == {"ガウス"}
