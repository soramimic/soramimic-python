"""Exact matching over pronunciation alternatives without expanding their product."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .kana_similarity import SimTable
from .kana_to_syllable import syllable_variations

# A switch between equivalent algorithms, never a limit on accepted alternatives.
_MAX_ENUMERATED_VARIATIONS = 256
_INF = float("inf")


class PronunciationSearch:
    """Keep alternatives per syllable and merge equivalent matching prefixes.

    Small queries can still use the vectorized enumerating matcher. Larger ones
    are scored over (syllable, output position, operation count) states, whose
    number grows polynomially rather than with the Cartesian product. Operation
    count stays separate from distance until the final addition, preserving the
    original floating-point evaluation order and position weights.
    """

    def __init__(self, target: list[str], lengths: Iterable[int]) -> None:
        self.levels = [
            (i, syllable_variations(syllable))
            for i, syllable in enumerate(target)
            if syllable is not None
        ]
        wanted = {length for length in lengths if length > 0}
        maximum = max(wanted, default=0)
        # Count only up to the algorithm switch; retain every reachable length.
        counts = {0: 1}
        limit = _MAX_ENUMERATED_VARIATIONS + 1
        for _, options in self.levels:
            next_counts: dict[int, int] = {}
            for prefix, count in counts.items():
                for units, _ in options:
                    size = prefix + len(units)
                    if size <= maximum:
                        next_counts[size] = min(limit, next_counts.get(size, 0) + count)
            counts = next_counts
        self.lengths = sorted(wanted.intersection(counts))
        # The small-query API enumerates every length up to max_units, including
        # lengths absent from the dictionary. Bound that whole allocation too.
        self.compact = sum(counts.values()) > _MAX_ENUMERATED_VARIATIONS

        self.suffix_min = [0] * (len(self.levels) + 1)
        self.suffix_max = [0] * (len(self.levels) + 1)
        for i in range(len(self.levels) - 1, -1, -1):
            sizes = [len(units) for units, _ in self.levels[i][1]]
            self.suffix_min[i] = self.suffix_min[i + 1] + min(sizes)
            self.suffix_max[i] = self.suffix_max[i + 1] + max(sizes)

    def score(
        self,
        pronunciation: list[str],
        kana_dist: SimTable,
        variation_cost: float = 0,
        word_cost: int = 0,
        unit_weights: Sequence[float] | None = None,
    ) -> float:
        """Return the same minimum score as enumerating every matching variant."""
        if not pronunciation or len(pronunciation) not in self.lengths:
            return _INF
        if any(unit not in kana_dist for unit in pronunciation):
            return _INF
        score = self._distance(pronunciation, kana_dist, variation_cost, word_cost, unit_weights)
        if unit_weights is not None and any(i >= len(unit_weights) for i, _ in self.levels):
            # _expand_weights ignores weights for a variant whose emitted src
            # includes an out-of-range index. A deleted syllable emits no src:
            # those variants must still retain their valid position weights.
            score = min(
                score,
                self._distance(
                    pronunciation,
                    kana_dist,
                    variation_cost,
                    word_cost,
                    None,
                    invalid_weight_count=len(unit_weights),
                ),
            )
        return score

    def _distance(
        self,
        pronunciation: list[str],
        kana_dist: SimTable,
        variation_cost: float,
        word_cost: int,
        weights: Sequence[float] | None,
        *,
        invalid_weight_count: int | None = None,
    ) -> float:
        length = len(pronunciation)
        # The flag is used only for the malformed-weight fallback above.
        states: dict[tuple[int, int, bool], float] = {(0, 0, False): 0.0}
        for level, (source, options) in enumerate(self.levels):
            remaining_min = self.suffix_min[level + 1]
            remaining_max = self.suffix_max[level + 1]
            next_states: dict[tuple[int, int, bool], float] = {}
            for (position, operations, invalid), distance in states.items():
                for units, cost in options:
                    end = position + len(units)
                    if end + remaining_min > length or end + remaining_max < length:
                        continue
                    if units and weights is not None and source >= len(weights):
                        continue
                    total = distance
                    for offset, unit in enumerate(units):
                        if unit not in kana_dist:
                            total = _INF
                            break
                        value = kana_dist[unit][pronunciation[position + offset]]
                        total += value if weights is None else value * weights[source]
                    if total == _INF:
                        continue
                    next_invalid = invalid or (
                        bool(units)
                        and invalid_weight_count is not None
                        and source >= invalid_weight_count
                    )
                    # With zero variation penalty, operation counts are equivalent.
                    key = (end, operations + cost if variation_cost else 0, next_invalid)
                    if total < next_states.get(key, _INF):
                        next_states[key] = total
            states = next_states
            if not states:
                return _INF
        return min(
            (
                distance + (operations + word_cost) * variation_cost if variation_cost else distance
                for (position, operations, invalid), distance in states.items()
                if position == length and (invalid_weight_count is None or invalid)
            ),
            default=_INF,
        )
