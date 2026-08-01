"""filler(万能候補)のテスト(#128)。本体JSの tests/filler.mjs と同じケースを見る。

単語が足りない(DUPLICATE=False で使い切った)・どの単語も合わない区間があると、
以前は行の変換結果が丸ごと空になっていた。DPに常設した filler
(1ユニットを必ず埋められる仮想語。表記も読みも元歌詞のかなそのまま)で
「変換しきれなかった部分は原曲のまま」という退化になったことを確認する。
"""

from __future__ import annotations

from typing import Any

import pytest

from soramimic.maker import FILLER_COST, SoramimiMaker

PARAM: dict[str, Any] = {
    "VOWEL_RATIO": 0.8,
    "VARIATION_COST": 20 * 0.8,
    "SAME_PHRASE_BREAK_REWARD": 0,
    "MID_PHRASE_BREAK_PENALTY": 20,
    "WORD_NUMBER_PENALTY": 20,
    "DUPLICATE": False,
}

Word = dict[str, Any]


def _units(pieces: dict[str, Any], phrase: str) -> list[str]:
    ta = pieces["text_analyzer"]
    return [
        u["pronunciation"] for u in ta.get_yomi_and_phrase_break(ta.tokenize_together([phrase])[0])
    ]


def _show(words: list[Word]) -> str:
    return "+".join(f"[{w['surface']}]" if w.get("filler") else w["surface"] for w in words)


def _assert_covered(words: list[Word], unit_count: int, label: str) -> None:
    """行が隙間なく単語で覆われていること(period が 0 から末尾まで連続する)。"""
    assert words, f"{label}: 行が空"
    cursor = 0
    for w in words:
        assert w["period"][0] == cursor, f"{label}: periodが連続していない"
        cursor = w["period"][1]
    assert cursor == unit_count, f"{label}: 行末まで覆われていない"


def _assert_filler(w: Word, kana: str, label: str) -> None:
    """filler の単語 dict が仕様どおりか(1ユニット・元かなそのまま・id無し)。"""
    assert w.get("filler") is True, f"{label}: fillerフラグ"
    assert w["period"][1] - w["period"][0] == 1, f"{label}: fillerは1ユニット"
    assert w["surface"] == kana, f"{label}: surfaceが元歌詞のかな"
    assert w["pronunciation"] == kana, f"{label}: pronunciationが元歌詞のかな"
    assert w["kana"] == kana, f"{label}: kanaが元歌詞のかな"
    assert w["originalkana"] == kana, f"{label}: originalkanaが元歌詞のかな"
    assert "id" not in w, f"{label}: fillerはidを持たない"
    assert not w["original"], f"{label}: fillerはoriginal(元表記)を持たない"


def test_filler_cost_matches_js() -> None:
    assert FILLER_COST == 1e6
    assert SoramimiMaker.FILLER_COST == FILLER_COST


# ---- 1. 単語を使い切っても行が空にならない -------------------------------


def test_no_empty_line_when_words_run_out(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("カキ\nキカ")
    units = _units(pieces, "カキ")
    assert units == ["カ", "キ"]

    results = maker.generate(["カキ", "カキ", "カキ"], db, PARAM)
    assert len(results) == 3
    for i, words in enumerate(results):
        _assert_covered(words, len(units), f"{i}行目")
    # 1・2行目は実単語(2語しかないので1語ずつ)、3行目は在庫切れでfillerになる
    assert all(not w.get("filler") for w in results[0]), "1行目は実単語で埋まる"
    assert all(not w.get("filler") for w in results[1]), "2行目は実単語で埋まる"
    assert results[0][0]["id"] != results[1][0]["id"], "単語重複なしが効いている"
    assert all(w.get("filler") for w in results[2]), "在庫切れの行はすべてfiller"
    for i, w in enumerate(results[2]):
        _assert_filler(w, units[i], f"3行目 filler{i}")


# ---- 2. 埋まる区間は実単語・埋まらない区間だけ1ユニットずつfiller ---------


def test_only_unfilled_span_becomes_filler(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("カキ")
    units = _units(pieces, "カキクケ")
    assert units == ["カ", "キ", "ク", "ケ"]

    line = maker.generate(["カキクケ"], db, PARAM)[0]
    _assert_covered(line, len(units), "混在行")
    assert _show(line) == "カキ+[ク]+[ケ]", _show(line)
    _assert_filler(line[1], "ク", "混在行 filler0")
    _assert_filler(line[2], "ケ", "混在行 filler1")


# ---- 3. 実単語が置ける位置でfillerが勝たない -----------------------------


@pytest.mark.parametrize(
    "param",
    [
        PARAM,
        {**PARAM, "WORD_NUMBER_PENALTY": 60, "MID_PHRASE_BREAK_PENALTY": 160},
    ],
    ids=["default_penalty", "max_penalty"],
)
@pytest.mark.parametrize(
    "weights",
    [None, [[4.0, 0.0, 0.0, 0.0]], [[0.0, 0.0, 2.0, 2.0]], [[0.1, 0.1, 3.8, 0.0]]],
    ids=["none", "head", "tail", "mid"],
)
def test_real_word_beats_filler(
    pieces: dict[str, Any], param: dict[str, Any], weights: list[list[float]] | None
) -> None:
    """重みは行内で平均1に正規化されるだけなので、片側に全振りしても実単語のコストは
    たかだか「距離の最大値80×ユニット数」で、fillerコスト(1e6)には遠く届かない。
    (重みの与え方で「どこに置くか」は変わりうるので、置かれる位置ではなく
     「実単語が1つ使われ、残りだけがfillerになる」ことを見る)
    """
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("カキ")
    units = _units(pieces, "カキクケ")

    line = maker.generate(["カキクケ"], db, param, weights_per_line=weights)[0]
    label = f"重み {weights} / ペナルティ{param['WORD_NUMBER_PENALTY']}"
    _assert_covered(line, len(units), label)
    real = [w for w in line if not w.get("filler")]
    assert len(real) == 1, f"{label}: 実単語が1つ使われる({_show(line)})"
    assert real[0]["surface"] == "カキ", f"{label}: 使われるのはリスト内の単語"
    fillers = [w for w in line if w.get("filler")]
    assert len(fillers) == len(units) - 2, f"{label}: 残りは1ユニットずつのfiller"
    for f in fillers:
        _assert_filler(f, units[f["period"][0]], f"{label} filler")


# ---- 4. fillerは使用済み判定の対象外(重複可) ----------------------------


def test_filler_is_not_consumed(pieces: dict[str, Any]) -> None:
    """3ユニットの語しかないリストは2ユニットの行のどこにも置けない(長さが違う語は
    候補にすらならない)ので、行全体がfillerになる。idを持たないので何行でも出る。
    """
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("クケコ")
    units = _units(pieces, "カキ")

    results = maker.generate(["カキ", "カキ", "カキ"], db, PARAM)
    assert len(results) == 3
    for i, words in enumerate(results):
        _assert_covered(words, len(units), f"{i}行目(全filler)")
        assert all(w.get("filler") for w in words), f"{i}行目はすべてfiller"
        for j, w in enumerate(words):
            _assert_filler(w, units[j], f"{i}行目 filler{j}")

    # 同一行内でも同じかなのfillerが並べる
    same = maker.generate(["カカ"], db, PARAM)
    assert _show(same[0]) == "[カ]+[カ]"


# ---- 5. 固定(locks)との共存 ---------------------------------------------


def test_filler_coexists_with_locks(pieces: dict[str, Any]) -> None:
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("カキ")
    units = _units(pieces, "カキクケ")
    tokens_list = ta.tokenize_together(["カキクケ"])

    locked = {
        "id": "lock-1",
        "surface": "ソラミミ",
        "pronunciation": "ソラ",
        "kana": "ソラ",
        "original": "ソラミミ",
        "sim": 0,
        "period": [1, 3],
    }
    line = maker.generate_from_tokens(tokens_list, db, PARAM, locks_per_line=[[dict(locked)]])[0]
    _assert_covered(line, len(units), "固定つき")
    assert _show(line) == "[カ]+ソラミミ+[ケ]", _show(line)
    _assert_filler(line[0], "カ", "固定つき filler0")
    _assert_filler(line[2], "ケ", "固定つき filler1")

    # 隙間に実単語が置けるなら、そちらが優先される(固定と共存しても同じ)
    locked2 = {**locked, "period": [2, 4]}
    line2 = maker.generate_from_tokens(tokens_list, db, PARAM, locks_per_line=[[locked2]])[0]
    assert _show(line2) == "カキ+ソラミミ", _show(line2)


# ---- 6. 下流(呼び出し側)がfiller混じりでも壊れない ----------------------


def test_output_shape_is_downstream_safe(pieces: dict[str, Any]) -> None:
    """fillerは id を持たないが、他の単語と同じフィールド(period/original_surface/
    score)を持つので、下流が行をそのまま走査しても壊れない。
    """
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("カキ")
    line = maker.generate(["カキクケ"], db, PARAM)[0]

    for w in line:
        assert w["original_surface"] == "".join(
            _units(pieces, "カキクケ")[w["period"][0] : w["period"][1]]
        )
        assert isinstance(w["score"], float)
    # 「使用単語の元表記一覧」相当: fillerは混ざらない
    originals = [w["original"] or w["surface"] for w in line if not w.get("filler")]
    assert originals == ["カキ"]


# ---- 既存挙動の不変(単語が足りていれば結果は従来と同一) ------------------


def test_sufficient_words_have_no_filler(pieces: dict[str, Any]) -> None:
    maker = pieces["maker"]
    db = pieces["word_list"].parse_plain("カキ\nキカ")
    results = maker.generate(["カキ", "キカ"], db, PARAM)
    assert [_show(line) for line in results] == ["カキ", "キカ"]
    assert all(not w.get("filler") for line in results for w in line)
