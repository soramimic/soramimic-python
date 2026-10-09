"""Compact pronunciation search preserves eager scores without enumerating paths."""

from __future__ import annotations

import importlib.util
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_similar_word_equivalence import naive_get_similar_word

from soramimic import pronunciation_search
from soramimic.kana_to_syllable import KanaToSyllable, Variation
from soramimic.maker import SoramimiMaker, _WordlistIndex
from soramimic.pronunciation_search import PronunciationSearch

SYLLABLES = (
    "ア",
    "カ",
    "ン",
    "ッ",
    "ンー",
    "ンッ",
    "カーン",
    "カンッ",
    "カーッ",
    "カー",
    "カッ",
    "カン",
    "カア",
    None,
)
INF = float("inf")


@pytest.fixture
def force_compact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pronunciation_search, "_MAX_ENUMERATED_VARIATIONS", 0)


def _eager_score(
    variations: list[Variation],
    pronunciation: list[str],
    kana_dist: dict[str, dict[str, float]],
    variation_cost: float,
    word_cost: int,
    weights: list[float] | None,
) -> float:
    """Use the pre-existing enumerator and scalar distance, not compact helpers."""
    scores = []
    for variation in variations:
        expanded = (
            None
            if weights is None or any(i >= len(weights) for i in variation.src)
            else [weights[i] for i in variation.src]
        )
        scores.append(
            SoramimiMaker._ld(variation, pronunciation, kana_dist, expanded)
            + (variation.vcost + word_cost) * variation_cost
        )
    return min(scores, default=INF)


def _distances() -> dict[str, dict[str, float]]:
    units = ("ア", "カ", "カー", "キ", "キー", "ン", "ッ")
    return {
        left: {
            right: 0.0 if left == right else (i * 7 + j + 1) / 13 for j, right in enumerate(units)
        }
        for i, left in enumerate(units)
    }


@pytest.mark.parametrize("weighted", [False, True])
def test_compact_score_exhaustive_syllable_pairs(force_compact: None, weighted: bool) -> None:
    converter = KanaToSyllable()
    kana_dist = _distances()
    weights = [0.0, 1.7] if weighted else None
    for pair in itertools.product(SYLLABLES, repeat=2):
        target: list[Any] = list(pair)
        variations = converter.get_variation(target)
        search = PronunciationSearch(target, range(1, 7))
        assert list(search.lengths) == sorted({len(v) for v in variations})
        pronunciations = {tuple(v) for v in variations} | {(), ("キ",), ("☃", "カ")}
        for pronunciation in pronunciations:
            for cost, word_cost in ((0.0, 0), (0.1, 3), (16.25, 1)):
                expected = _eager_score(
                    variations, list(pronunciation), kana_dist, cost, word_cost, weights
                )
                actual = search.score(list(pronunciation), kana_dist, cost, word_cost, weights)
                assert actual == expected, (target, pronunciation, cost, word_cost, weights)


def test_compact_score_randomized_float_order(force_compact: None) -> None:
    rng = random.Random(71927)
    converter = KanaToSyllable()
    units = list(_distances())
    kana_dist = {
        left: {right: rng.choice([0.0, 0.1, 1 / 3, 1e-12, 1e12, 2**53]) for right in units}
        for left in units
    }
    for _ in range(160):
        target: list[Any] = [rng.choice(SYLLABLES) for _ in range(rng.randrange(1, 7))]
        variations = converter.get_variation(target)
        search = PronunciationSearch(target, range(1, 19))
        weights = rng.choice([None, [rng.choice([0.0, 0.3, 1.0, 1.9]) for _ in target]])
        pronunciation = list(rng.choice(variations)) if variations else []
        if pronunciation:
            pronunciation[rng.randrange(len(pronunciation))] = rng.choice([*units, "☃"])
        cost = rng.choice([0.0, 0.1, 0.7, 16.25, -0.125])
        word_cost = rng.randrange(5)
        assert search.score(pronunciation, kana_dist, cost, word_cost, weights) == _eager_score(
            variations, pronunciation, kana_dist, cost, word_cost, weights
        ), (target, pronunciation, cost, word_cost, weights)


def test_compact_adds_each_unit_before_combined_variation_penalty(force_compact: None) -> None:
    target = ["カンッ", "キンッ"]
    kana_dist = _distances()
    for row in kana_dist.values():
        for unit in row:
            row[unit] = 1.0
    kana_dist["カ"]["カ"] = 1e16
    kana_dist["カー"]["カー"] = 1e16
    variations = KanaToSyllable().get_variation(target)
    search = PronunciationSearch(target, [2, 6])
    for pronunciation in (["カ", "ン", "ッ", "キ", "ン", "ッ"], ["カー", "キー"]):
        expected = _eager_score(variations, pronunciation, kana_dist, 0.75, 1, None)
        assert search.score(pronunciation, kana_dist, 0.75, 1) == expected


@pytest.mark.parametrize("target", [[], [None], [None, None], [""], ["ン", "ッ"], ["カン"]])
def test_reachable_dictionary_lengths(target: list[Any]) -> None:
    variations = KanaToSyllable().get_variation(target)
    lengths = [7, 2, 0, 1, 2, -1]
    search = PronunciationSearch(target, iter(lengths))
    assert list(search.lengths) == sorted({len(v) for v in variations} & set(lengths))


def test_compact_threshold_keeps_ordinary_search_small() -> None:
    assert not PronunciationSearch(["カン"], [1, 2]).compact
    assert not PronunciationSearch(["カン"] * 6, [6]).compact
    assert PronunciationSearch(["カン"] * 6, range(6, 13)).compact
    # Even one reachable bucket can require too many eager intermediate variants.
    assert PronunciationSearch(["カン"] * 6, [12]).compact


@pytest.mark.parametrize("weights", [[], [0.0], [7.0]])
def test_partial_weights_fall_back_only_for_variants_with_invalid_sources(
    force_compact: None, weights: list[float]
) -> None:
    target = ["カン", "ン", "ッ"]
    variations = KanaToSyllable().get_variation(target)
    search = PronunciationSearch(target, range(1, 5))
    kana_dist = _distances()
    for pronunciation in (["キ"], ["キ", "ン"], ["キー", "ッ"], ["キ", "ン", "ッ"]):
        expected = _eager_score(variations, pronunciation, kana_dist, 0.3, 1, weights)
        assert search.score(pronunciation, kana_dist, 0.3, 1, weights) == expected


@pytest.mark.parametrize("target", [["☃", "カ"], [None, "カン", None, "キッ"]])
def test_unknown_or_skipped_source_with_zero_weight(force_compact: None, target: list[Any]) -> None:
    weights = [0.0, 1.7, 99.0, 0.3][: len(target)]
    kana_dist = _distances()
    variations = KanaToSyllable().get_variation(target)
    search = PronunciationSearch(target, range(1, 7))
    for pronunciation in (["カ", "カ"], ["カ", "ン", "キ", "ッ"], ["☃", "カ"]):
        expected = _eager_score(variations, pronunciation, kana_dist, 0.3, 2, weights)
        assert search.score(pronunciation, kana_dist, 0.3, 2, weights) == expected


def _word(word_id: str, pronunciation: list[str], label: str, cost: int = 0) -> dict[str, Any]:
    return {
        "id": word_id,
        "surface": label,
        "original": label,
        "kana": "".join(pronunciation),
        "pronunciation": pronunciation,
        "vcost": cost,
    }


@pytest.mark.parametrize("target", [["カン", "キッ"], ["ンッ", "カア"], [None, "カン", "ッ"]])
@pytest.mark.parametrize("weighted", [False, True])
def test_compact_ranking_and_exclusions_match_eager_oracle(
    pieces: dict[str, Any], force_compact: None, target: list[Any], weighted: bool
) -> None:
    maker = pieces["maker"]
    kana_dist = _distances()
    variants = KanaToSyllable().get_variation(target)
    ids = ("10", "z", "2", "01", "2", "a", "z")
    db: dict[int, list[dict[str, Any]]] = {}
    for i, variant in enumerate(variants):
        db.setdefault(len(variant), []).append(
            _word(ids[i % len(ids)], list(variant), f"entry-{i}", i % 3)
        )
    key = min(db)
    # A malformed bucket remains infinite even if the actual length is reachable.
    db[key].append(_word("mismatch", ["カ"] * (key + 1), "length mismatch"))
    db[key].append(_word("unknown", ["☃"] * key, "unknown unit"))
    db[99] = [_word("unreachable", ["カ"] * 99, "unreachable length")]
    weights = [0.0] + [1.7] * (len(target) - 1) if weighted else None
    for cost in (0.0, 0.3, 16.25):
        expected = naive_get_similar_word(maker, db, target, kana_dist, cost, weights)
        actual = maker.get_similar_word(db, target, kana_dist, 100, cost, weights)
        assert actual == expected
        for excluded in (set(), {"2", "10"}, {word["id"] for word in expected}):
            index = _WordlistIndex(db, kana_dist)
            best = maker._get_best_available_word(index, target, kana_dist, excluded, cost, weights)
            assert best == [word for word in expected if word["id"] not in excluded][:1]
            assert index._cache == {}


def test_compact_duplicate_ties_across_entry_chunks(
    pieces: dict[str, Any], force_compact: None
) -> None:
    maker = pieces["maker"]
    kana_dist = _distances()
    target = ["カン", "カン"]
    pronunciation = ["カ", "カ"]
    entries = [_word("z", pronunciation, "first nonnumeric")]
    entries += [_word("10", pronunciation, f"entry-{i}") for i in range(260)]
    entries += [
        _word("2", pronunciation, "numeric first"),
        _word("01", pronunciation, "leading zero"),
        _word("2", pronunciation, "numeric last"),
        _word("a", pronunciation, "last nonnumeric"),
    ]
    db = {2: entries}
    expected = naive_get_similar_word(maker, db, target, kana_dist, 0.25)
    assert [word["id"] for word in expected] == ["2", "10", "z", "01", "a"]
    assert expected[0]["surface"] == "numeric last"
    assert maker.get_similar_word(db, target, kana_dist, variation_cost=0.25) == expected
    excluded: set[str] = set()
    for wanted in expected:
        best = maker._get_best_available_word(
            _WordlistIndex(db, kana_dist), target, kana_dist, excluded, 0.25
        )
        assert best == [wanted]
        excluded.add(wanted["id"])


@pytest.mark.skipif(importlib.util.find_spec("resource") is None, reason="requires resource limits")
def test_long_branching_query_has_bounded_allocation() -> None:
    """A reachable 3**36-path query must complete within a generous hard bound."""
    script = """
import json
import resource
import tracemalloc
from types import SimpleNamespace

from soramimic.kana_to_syllable import KanaToSyllable
from soramimic.maker import SoramimiMaker, _WordlistIndex

resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
converter = KanaToSyllable()
maker = SoramimiMaker(None, SimpleNamespace(syllable_to_variation=converter.get_variation))
target = ["カン"] * 36
units = ["カ", "カー", "ン"]
distances = {left: {right: float(left != right) for right in units} for left in units}
db = {
    36: [{"id": "10", "pronunciation": ["カ"] * 36, "vcost": 0}],
    54: [{"id": "2", "pronunciation": ["カ", "ン"] * 18 + ["カ"] * 18, "vcost": 0}],
}
tracemalloc.start()
full = maker.get_similar_word(db, target, distances, variation_cost=0.125)
best = maker._get_best_available_word(_WordlistIndex(db, distances), target, distances, set(), 0.125)
next_best = maker._get_best_available_word(
    _WordlistIndex(db, distances), target, distances, {"2"}, 0.125
)
_, peak = tracemalloc.get_traced_memory()
print(json.dumps({"full": full, "best": best, "next_best": next_best, "peak": peak}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert [(word["id"], word["sim"]) for word in report["full"]] == [("2", 2.25), ("10", 4.5)]
    assert report["best"] == report["full"][:1]
    assert report["next_best"] == report["full"][1:]
    assert report["peak"] < 32 * 1024**2
