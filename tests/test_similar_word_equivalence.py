"""get_similar_word の高速経路が、素朴な実装とビット単位で一致することのテスト。

get_similar_word は「候補(歌詞側の発音バリエーション)× 単語DBのバケツ」を
ユニット位置ごとの列でまとめて処理する。ここでは移植元 soramimic.js のとおりに
単語ごとに ld を呼ぶだけの参照実装を置き、両者の出力(sim の float 値まで)が
完全に一致することを、速い経路が使われない条件も含めて確かめる。
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from soramimic.kana_to_syllable import Variation
from soramimic.maker import SoramimiMaker
from soramimic.utils import js_object_key_order

INF = float("inf")


def naive_get_similar_word(
    maker: SoramimiMaker,
    wordlist: dict[int, list[dict[str, Any]]],
    target: list[str],
    kana_dist: dict[str, dict[str, float]],
    variation_cost: float = 0,
    unit_weights: list[float] | None = None,
) -> list[dict[str, Any]]:
    """移植元 soramimic.js の getSimilarWord をそのまま写した参照実装。"""
    tmp = maker.text_analyzer.syllable_to_variation(target)
    candidates: dict[int, list[Variation]] = {}
    candidate_weights: dict[int, list[list[float] | None]] = {}
    for c in tmp:
        clen = len(c)
        if clen not in wordlist:
            continue
        candidates.setdefault(clen, [])
        candidate_weights.setdefault(clen, [])
        candidates[clen].append(c)
        candidate_weights[clen].append(maker._expand_weights(c, unit_weights))

    words: dict[str, dict[str, Any]] = {}
    for i in js_object_key_order([str(k) for k in candidates.keys()]):
        key = int(i)
        for w in wordlist[key]:
            sim = INF
            for ci, c in enumerate(candidates[key]):
                d = (
                    maker._ld(c, w["pronunciation"], kana_dist, candidate_weights[key][ci])
                    + ((getattr(c, "vcost", 0) or 0) + (w.get("vcost") or 0)) * variation_cost
                )
                sim = min(d, sim)
            wid = w["id"]
            if wid in words and sim > words[wid]["sim"]:
                continue
            words[wid] = {**w, "sim": sim}

    words2 = [words[wid] for wid in js_object_key_order(list(words.keys()))]
    words2.sort(key=lambda a: a["sim"])
    return words2


def _assert_same(got: list[dict[str, Any]], want: list[dict[str, Any]]) -> None:
    assert [w["id"] for w in got] == [w["id"] for w in want]
    assert [w["surface"] for w in got] == [w["surface"] for w in want]
    for g, e in zip(got, want, strict=True):
        # 浮動小数はビット一致(nan は出ない前提)まで見る
        assert g["sim"] == e["sim"] or (math.isnan(g["sim"]) and math.isnan(e["sim"]))
        assert g.keys() == e.keys()


CSV = (
    "id,original,surface,pronunciation\n"
    "1,ネコ,ネコ,ネコ\n"
    "2,イヌ,イヌ,イヌ\n"
    "3,カード,カード,カード\n"
    "4,タイヨウ,タイヨウ,タイヨウ\n"
    "5,カンナ,カンナ,カンナ\n"
    "6,カッタ,カッタ,カッタ\n"
    "7,ネッコ,ネッコ,ネッコ\n"
    "8,ネコー,ネコー,ネコー"
)

TARGETS = [
    ["ネ", "コ"],
    ["カ", "ン", "ナ"],
    ["カ", "ッ", "タ"],
    ["タ", "イ", "ヨ", "ウ"],
    ["ネ"],
]


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("variation_cost", [0, 3, 20 * 0.8])
def test_matches_naive(pieces: dict[str, Any], target: list[str], variation_cost: float) -> None:
    maker = pieces["maker"]
    db = pieces["word_list"].parse_tidy(CSV, "")
    kana_dist = pieces["kana_similarity"].get_kana_similarity({})
    got = maker.get_similar_word(db, target, kana_dist, 100, variation_cost)
    want = naive_get_similar_word(maker, db, target, kana_dist, variation_cost)
    _assert_same(got, want)


@pytest.mark.parametrize("target", TARGETS)
def test_matches_naive_with_unit_weights(pieces: dict[str, Any], target: list[str]) -> None:
    maker = pieces["maker"]
    db = pieces["word_list"].parse_tidy(CSV, "")
    kana_dist = pieces["kana_similarity"].get_kana_similarity({})
    # 0 を含む重み(未知ユニットの Infinity に掛けると nan になる組み合わせ)も試す
    for pattern in ([1.0] * len(target), [0.0] + [1.5] * (len(target) - 1)):
        weights = pattern[: len(target)]
        got = maker.get_similar_word(db, target, kana_dist, 100, 16.0, weights)
        want = naive_get_similar_word(maker, db, target, kana_dist, 16.0, weights)
        _assert_same(got, want)


def test_matches_naive_with_unknown_unit_in_wordlist(pieces: dict[str, Any]) -> None:
    """kana_dist に無いユニットを含む単語が混ざっていても素朴版と一致する。

    実データ(学者リストなど)で起きるケース。該当単語だけ Infinity になり、
    同じバケツの他の単語は通常どおり計算されなければならない。
    """
    maker = pieces["maker"]
    db = pieces["word_list"].parse_tidy(CSV, "")
    kana_dist = pieces["kana_similarity"].get_kana_similarity({})
    db[2] = [
        *db[2],
        {
            "surface": "X",
            "pronunciation": ["ネ", "☃"],
            "kana": "ネ☃",
            "id": "99",
            "original": "X",
            "vcost": 0,
        },
    ]

    for variation_cost in (0, 16.0):
        got = maker.get_similar_word(db, ["ネ", "コ"], kana_dist, 100, variation_cost)
        want = naive_get_similar_word(maker, db, ["ネ", "コ"], kana_dist, variation_cost)
        _assert_same(got, want)
    assert any(w["id"] == "99" and w["sim"] == INF for w in got)


def test_matches_naive_with_length_mismatch_in_bucket(pieces: dict[str, Any]) -> None:
    """バケツのキーとユニット数が食い違う単語(_ld が長さ不一致で Infinity)も一致する。"""
    maker = pieces["maker"]
    db = pieces["word_list"].parse_tidy(CSV, "")
    kana_dist = pieces["kana_similarity"].get_kana_similarity({})
    db[2] = [
        *db[2],
        {
            "surface": "Y",
            "pronunciation": ["ネ"],
            "kana": "ネ",
            "id": "98",
            "original": "Y",
            "vcost": 0,
        },
    ]

    got = maker.get_similar_word(db, ["ネ", "コ"], kana_dist, 100, 16.0)
    want = naive_get_similar_word(maker, db, ["ネ", "コ"], kana_dist, 16.0)
    _assert_same(got, want)


def test_generate_from_tokens_shares_index(pieces: dict[str, Any]) -> None:
    """generate_from_tokens が使う内部インデックス経由でも結果が変わらない。"""
    ta = pieces["text_analyzer"]
    maker = pieces["maker"]
    db = pieces["word_list"].parse_tidy(CSV, "")
    tokens_list = ta.tokenize_together(["ネコカード", "カンナ", "ネコ"])
    param = {"DUPLICATE": False, "VARIATION_COST": 16.0, "MID_PHRASE_BREAK_PENALTY": 20}
    a = maker.generate_from_tokens(tokens_list, db, dict(param))
    b = maker.generate_from_tokens(tokens_list, db, dict(param))
    assert [[(w["id"], w["sim"], w["score"]) for w in line] for line in a] == [
        [(w["id"], w["sim"], w["score"]) for w in line] for line in b
    ]
