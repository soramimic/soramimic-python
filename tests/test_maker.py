"""maker の generate_from_tokens / get_candidates が決定的な結果を返すことのテスト。"""

from __future__ import annotations

from typing import Any


def _build_db(pieces: dict[str, Any]) -> Any:
    wl = pieces["word_list"]
    csv = (
        "id,original,surface,pronunciation\n"
        "1,ネコ,ネコ,ネコ\n"
        "2,イヌ,イヌ,イヌ\n"
        "3,カード,カード,カード\n"
        "4,タイヨウ,タイヨウ,タイヨウ"
    )
    return wl.parse_tidy(csv, "")


def test_generate_from_tokens_deterministic(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = _build_db(pieces)

    tokens_list = ta.tokenize_together(["ネコカード", "タイヨウ"])
    results = maker.generate_from_tokens(tokens_list, db, {})

    ids = [[(w["surface"], w["id"]) for w in line] for line in results]
    assert ids == [[("ネコ", "1"), ("カード", "3")], [("タイヨウ", "4")]]

    # original_surface / period / score が付与される
    first = results[0][0]
    assert first["period"] == [0, 2]
    assert first["original_surface"] == "ネコ"
    assert "score" in first and "sim" in first


def test_generate_returns_results(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = _build_db(pieces)
    results = maker.generate(["ネコ"], db, {})
    assert isinstance(results, list)
    assert results[0][0]["surface"] == "ネコ"


def test_get_candidates(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = _build_db(pieces)
    cands = maker.get_candidates(db, ["ネ", "コ"], {}, 5)
    # 最も近いのは ネコ、次いで長さ2の候補が sim 昇順で並ぶ
    assert cands[0]["surface"] == "ネコ"
    assert [c["surface"] for c in cands] == ["ネコ", "カード", "イヌ"]
    # コピーを返す(呼び出し側の編集が DB を汚さない)
    cands[0]["surface"] = "MUT"
    assert db[2][0]["surface"] != "MUT"


def test_generate_no_duplicate(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = _build_db(pieces)
    tokens_list = ta.tokenize_together(["ネコネコ"])
    # DUPLICATE=False で同じ単語の重複採用を避ける
    results = maker.generate_from_tokens(tokens_list, db, {"DUPLICATE": False})
    line = results[0]
    ids = [w["id"] for w in line]
    assert len(ids) == len(set(ids))
