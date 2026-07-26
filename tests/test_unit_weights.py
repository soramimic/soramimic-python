"""ユニット位置別の重み付きスコアリング(weights_per_line)のテスト。"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from soramimic.kana_to_syllable import KanaToSyllable
from soramimic.maker import normalize_unit_weights


def _build_db(pieces: dict[str, Any]) -> Any:
    """カコ/コカ(どちらも2音節)だけの単語リスト。

    ターゲット「カカ」に対し、カコは位置0が完全一致、コカは位置1が完全一致で、
    距離は対称なので重みなしでは同点になる。
    """
    wl = pieces["word_list"]
    csv = "id,original,surface,pronunciation\n1,カコ,カコ,カコ\n2,コカ,コカ,コカ"
    return wl.parse_tidy(csv, "")


def _sim_of(words: list[dict[str, Any]], surface: str) -> float:
    return next(w["sim"] for w in words if w["surface"] == surface)


# --- 正規化 ---------------------------------------------------------------


def test_normalize_mean_is_one() -> None:
    out = normalize_unit_weights([1.0, 3.0], 2)
    assert out == [0.5, 1.5]
    assert sum(out) == pytest.approx(2.0)  # 平均1


def test_normalize_keeps_all_ones() -> None:
    assert normalize_unit_weights([1.0, 1.0, 1.0], 3) == [1.0, 1.0, 1.0]


def test_normalize_scale_invariant() -> None:
    # 全体を定数倍しても正規化後は同じ(定数項との相対スケールが保たれる)
    assert normalize_unit_weights([2.0, 6.0], 2) == normalize_unit_weights([1.0, 3.0], 2)


def test_normalize_none_passthrough() -> None:
    assert normalize_unit_weights(None, 3) is None


def test_normalize_length_mismatch_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert normalize_unit_weights([1.0, 2.0], 3) is None
    assert "length mismatch" in caplog.text


def test_normalize_zero_sum_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert normalize_unit_weights([0.0, 0.0], 2) is None
    assert "sum" in caplog.text


def test_normalize_negative_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert normalize_unit_weights([-1.0, 3.0], 2) is None
    assert "invalid unit weight" in caplog.text


def test_normalize_non_finite_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert normalize_unit_weights([float("inf"), 1.0], 2) is None
    assert "invalid unit weight" in caplog.text


# --- 省略時は従来どおり ---------------------------------------------------


def test_weights_none_is_identical(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = _build_db(pieces)

    base = maker.generate_from_tokens(ta.tokenize_together(["カカ", "コカ"]), db, {})
    explicit_none = maker.generate_from_tokens(
        ta.tokenize_together(["カカ", "コカ"]), db, {}, weights_per_line=None
    )
    assert explicit_none == base


def test_uniform_weights_match_unweighted(pieces: dict[str, Any]) -> None:
    """全ユニット同じ重み(正規化後は全1)なら重みなしと同じスコアになる。"""
    maker = pieces["maker"]
    db = _build_db(pieces)
    kana_dist = pieces["kana_similarity"].get_kana_similarity(maker._assign_default_parameter({}))

    plain = maker.get_similar_word(db, ["カ", "カ"], kana_dist, 100, 0)
    uniform = maker.get_similar_word(
        db, ["カ", "カ"], kana_dist, 100, 0, normalize_unit_weights([3.0, 3.0], 2)
    )
    assert [(w["id"], w["sim"]) for w in uniform] == [(w["id"], w["sim"]) for w in plain]


# --- 重みで選択が変わる ---------------------------------------------------


def test_weight_shifts_score_direction(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = _build_db(pieces)
    kana_dist = pieces["kana_similarity"].get_kana_similarity(maker._assign_default_parameter({}))

    a = kana_dist["カ"]["カ"]  # 一致
    b = kana_dist["カ"]["コ"]  # 母音違い
    assert a < b

    plain = maker.get_similar_word(db, ["カ", "カ"], kana_dist, 100, 0)
    assert _sim_of(plain, "カコ") == pytest.approx(a + b)
    assert _sim_of(plain, "コカ") == pytest.approx(a + b)  # 重みなしでは同点

    # 位置0を重くすると(正規化後 [1.5, 0.5])、位置0が一致している カコ が有利になる
    heavy_head = maker.get_similar_word(
        db, ["カ", "カ"], kana_dist, 100, 0, normalize_unit_weights([3.0, 1.0], 2)
    )
    assert _sim_of(heavy_head, "カコ") == pytest.approx(1.5 * a + 0.5 * b)
    assert _sim_of(heavy_head, "コカ") == pytest.approx(1.5 * b + 0.5 * a)
    assert _sim_of(heavy_head, "カコ") < _sim_of(heavy_head, "コカ")

    # 位置1を重くすると逆転する
    heavy_tail = maker.get_similar_word(
        db, ["カ", "カ"], kana_dist, 100, 0, normalize_unit_weights([1.0, 3.0], 2)
    )
    assert _sim_of(heavy_tail, "コカ") == pytest.approx(1.5 * a + 0.5 * b)
    assert _sim_of(heavy_tail, "コカ") < _sim_of(heavy_tail, "カコ")


def test_weight_changes_selected_word(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = _build_db(pieces)

    def run(weights: list[list[float]] | None) -> str:
        results = maker.generate_from_tokens(
            ta.tokenize_together(["カカ"]), db, {}, weights_per_line=weights
        )
        return results[0][0]["surface"]

    assert run([[3.0, 1.0]]) == "カコ"
    assert run([[1.0, 3.0]]) == "コカ"
    # 不正な重み(長さ不一致)は重みなしにフォールバックし、例外にはならない
    assert run([[1.0, 1.0, 1.0]]) == run(None)


def test_weights_do_not_leak_across_lines(pieces: dict[str, Any]) -> None:
    """同じカナ列の行でも、行ごとの重みでキャッシュが汚染されない。"""
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = _build_db(pieces)

    results = maker.generate_from_tokens(
        ta.tokenize_together(["カカ", "カカ", "カカ"]),
        db,
        {},
        weights_per_line=[[3.0, 1.0], [1.0, 3.0], [3.0, 1.0]],
    )
    assert [line[0]["surface"] for line in results] == ["カコ", "コカ", "カコ"]


# --- 変種展開を跨いだ重み対応 ---------------------------------------------


def test_variation_src_tracks_source_syllable() -> None:
    k2s = KanaToSyllable()
    syllables = k2s.split("カンコ")
    assert syllables == ["カン", "コ"]
    variations = k2s.get_variation(syllables)
    got = {tuple(v): list(v.src) for v in variations}
    # ン残し(3ユニット)・ン→ー化・ン削除(いずれも2ユニット)
    assert got == {
        ("カ", "ン", "コ"): [0, 0, 1],
        ("カー", "コ"): [0, 1],
        ("カ", "コ"): [0, 1],
    }


def test_variation_src_for_bare_n_deletion() -> None:
    k2s = KanaToSyllable()
    # 裸のンは削除されうる(ユニット数が減り、後続の対応がずれないこと)
    variations = k2s.get_variation(["カ", "ン", "コ"])
    got = {tuple(v): list(v.src) for v in variations}
    assert got[("カ", "ン", "コ")] == [0, 1, 2]
    assert got[("カ", "コ")] == [0, 2]


def test_weights_follow_variation_expansion(pieces: dict[str, Any]) -> None:
    """ン残し変種(音節2つ→ユニット3つ)でも重みが元の音節位置に対応する。"""
    maker = pieces["maker"]
    wl = pieces["word_list"]
    kana_dist = pieces["kana_similarity"].get_kana_similarity(maker._assign_default_parameter({}))
    # 3ユニットの単語だけを置くと、変種 ["カ","ン","カ"](src=[0,0,1])だけが
    # 突き合わせ対象になる(候補はユニット数で単語リストと突き合わせるため)
    db = wl.parse_tidy(
        "id,original,surface,pronunciation\n1,カコカ,カコカ,カコカ\n2,ココカ,ココカ,ココカ", ""
    )
    assert list(db.keys()) == [3]
    pron = {w["surface"]: w["pronunciation"] for w in db[3]}
    assert pron["カコカ"] == ["カ", "コ", "カ"]

    target = ["カン", "カ"]  # 音節2つ。ユニット0,1が音節0、ユニット2が音節1に対応
    unit = ["カ", "ン", "カ"]

    def expected(surface: str, unit_weights: list[float]) -> float:
        p = pron[surface]
        return sum(kana_dist[unit[i]][p[i]] * unit_weights[i] for i in range(3))

    plain = maker.get_similar_word(db, target, kana_dist, 100, 0)
    assert _sim_of(plain, "カコカ") == pytest.approx(expected("カコカ", [1, 1, 1]))

    # 音節0を重くする → ユニット0と1の両方が 2倍、ユニット2は 0倍になる
    heavy_head = maker.get_similar_word(
        db, target, kana_dist, 100, 0, normalize_unit_weights([2.0, 0.0], 2)
    )
    for surface in ("カコカ", "ココカ"):
        assert _sim_of(heavy_head, surface) == pytest.approx(expected(surface, [2, 2, 0]))
        # ユニットindexにそのまま重みを当てる誤実装([2,0,0])とは別の値になる
        assert _sim_of(heavy_head, surface) != pytest.approx(expected(surface, [2, 0, 0]))

    # 音節1を重くする → ユニット2だけが 2倍
    heavy_tail = maker.get_similar_word(
        db, target, kana_dist, 100, 0, normalize_unit_weights([0.0, 2.0], 2)
    )
    for surface in ("カコカ", "ココカ"):
        assert _sim_of(heavy_tail, surface) == pytest.approx(expected(surface, [0, 0, 2]))

    # 先頭ユニットで差がつく組み合わせなので、音節0を重くすると順序が変わる
    assert _sim_of(heavy_head, "カコカ") < _sim_of(heavy_head, "ココカ")
    assert _sim_of(heavy_tail, "カコカ") == pytest.approx(_sim_of(heavy_tail, "ココカ"))
