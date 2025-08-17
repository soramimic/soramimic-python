"""
Allocator module for text correspondence calculation.

This module provides functional        # 型が異なる場合は False
        if type(object1) is not type(object2):
            return False

        # プリミティブ型は直接比較
        if isinstance(object1, type(None) | bool | int | float | str):
            return object1 == object2

        # リスト（配列）の比較
        elif isinstance(object1, list):
            if len(object1) != len(object2):
                return False
            return all(
                cls._is_same_object(item1, item2)
                for item1, item2 in zip(object1, object2, strict=True)
            )mal text correspondences
using dynamic programming approach.
"""

import logging
from collections.abc import Callable
from typing import Any

# ロガー設定
logger = logging.getLogger(__name__)


class Allocator:
    """
    Text allocation class for finding optimal correspondences between texts.

    This class implements dynamic programming algorithms to find optimal
    mappings between two text sequences using a provided conversion function.
    """

    def __init__(self) -> None:
        """Initialize the Allocator instance."""
        logger.debug("Allocator instance created")

    @staticmethod
    def result2string(
        result: list[tuple[int, int, int, int]], text1: str, text2: str
    ) -> list[tuple[str, str]]:
        """
        Convert result indices to actual text strings.

        Args:
            result: List of tuples with start and length indices
            text1: First text string
            text2: Second text string

        Returns:
            List of string pairs corresponding to the indices
        """
        logger.debug(
            f"Converting result to strings for texts of length "
            f"{len(text1)}, {len(text2)}"
        )
        if text1 == "" or text2 == "":
            return [(text1, text2)]

        str_result = []
        for s1, l1, s2, l2 in result:
            str_result.append((text1[s1 : s1 + l1], text2[s2 : s2 + l2]))

        logger.debug(f"Converted {len(result)} indices to string pairs")
        return str_result

    class _Memo:
        """Memoization helper class for dynamic programming."""

        def __init__(self) -> None:
            """Initialize the memoization storage."""
            self.m: dict[int, dict[int, dict[int, dict[int, Any]]]] = {}

        def get(self, s1: int, l1: int, s2: int, l2: int, default: Any = None) -> Any:
            """Get cached value."""
            if (
                s1 in self.m
                and l1 in self.m[s1]
                and s2 in self.m[s1][l1]
                and l2 in self.m[s1][l1][s2]
            ):
                return self.m[s1][l1][s2][l2]
            return default

        def has(self, s1: int, l1: int, s2: int, l2: int) -> bool:
            """Check if value is cached."""
            return (
                s1 in self.m
                and l1 in self.m[s1]
                and s2 in self.m[s1][l1]
                and l2 in self.m[s1][l1][s2]
            )

        def set(self, s1: int, l1: int, s2: int, l2: int, value: Any) -> None:
            """Cache a value."""
            if s1 not in self.m:
                self.m[s1] = {}
            if l1 not in self.m[s1]:
                self.m[s1][l1] = {}
            if s2 not in self.m[s1][l1]:
                self.m[s1][l1][s2] = {}
            self.m[s1][l1][s2][l2] = value

    def _check_boundary_conditions(  # noqa: PLR0913
        self,
        memo: "_Memo",
        s1: int,
        l1: int,
        s2: int,
        l2: int,
        text1: str,
        text2: str,
        t1: str,
        t2: str,
        converted_t1: str | None,
    ) -> tuple[bool, bool, tuple[float, list[tuple[int, int, int, int]]] | None]:
        """
        Check boundary conditions for dynamic programming.

        Returns:
            Tuple of (is_zero_cost, is_infinity, early_return_result)
        """
        is_zero_cost = False
        is_infinity = False
        early_return = None

        # 境界条件のチェック
        if memo.get(0, s1, 0, s2, [0])[0] == float("inf") or memo.get(
            s1 + l1, len(text1) - s1 - l1, s2 + l2, len(text2) - s2 - l2, [0]
        )[0] == float("inf"):
            is_infinity = True
        elif l1 == 0 and l2 == 0:
            result = (0, [])
            memo.set(s1, l1, s2, l2, result)
            early_return = result
        elif l1 == 0:  # l1のみ0のとき
            is_infinity = True  # 空文字が非空文字と対応することはないので
        elif l1 == 1:
            if converted_t1 is None:  # 1要素を変換できなかったら
                if t1 == t2:
                    is_zero_cost = True
                else:
                    is_infinity = True
            elif converted_t1 == t2:
                is_zero_cost = True
            else:
                is_infinity = True
        elif converted_t1 is not None and converted_t1 == t2:
            is_zero_cost = True

        return is_zero_cost, is_infinity, early_return

    def find_correspondence(
        self, text1: str, text2: str, convert_func: Callable[[str], str | None]
    ) -> tuple[float, list[tuple[int, int, int, int]]]:
        """
        Find optimal correspondence between two texts using dynamic programming.

        Args:
            text1: First text to compare
            text2: Second text to compare
            convert_func: Function to convert text1 segments to text2 format

        Returns:
            Tuple of (cost, correspondence_list) where correspondence_list contains
            tuples of (start1, length1, start2, length2)
        """
        logger.info(
            f"Finding correspondence between texts of length "
            f"{len(text1)} and {len(text2)}"
        )

        memo = self._Memo()

        def dp(
            s1: int, l1: int, s2: int, l2: int
        ) -> tuple[float, list[tuple[int, int, int, int]]]:
            """Dynamic programming function for finding optimal alignment."""
            # 過去に計算したことがあればその結果を返す
            if memo.has(s1, l1, s2, l2):
                return memo.get(s1, l1, s2, l2)

            t1 = text1[s1 : s1 + l1]
            t2 = text2[s2 : s2 + l2]
            converted_t1 = convert_func(t1)

            # 境界条件のチェック
            is_zero_cost, is_infinity, early_return = self._check_boundary_conditions(
                memo, s1, l1, s2, l2, text1, text2, t1, t2, converted_t1
            )

            if early_return is not None:
                return early_return

            if is_zero_cost:
                result = (0, [(s1, l1, s2, l2)])
                memo.set(s1, l1, s2, l2, result)
                return result
            elif is_infinity:
                result = (float("inf"), [(s1, l1, s2, l2)])
                memo.set(s1, l1, s2, l2, result)
                # もし(s1,l1,s2,l2)が端の区間だったら残りの要素もinfにする
                if s1 + s2 + l1 + l2 == len(text1) + len(text2) and s1 + s2 > 0:
                    memo.set(0, s1, 0, s2, (float("inf"), [(0, s1, 0, s2)]))
                elif s1 + s2 == 0 and l1 + l2 < len(text1) + len(text2):
                    memo.set(
                        s1 + l1,
                        len(text1) - s1 - l1,
                        s2 + l2,
                        len(text2) - s2 - l2,
                        (
                            float("inf"),
                            [
                                (
                                    s1 + l1,
                                    len(text1) - s1 - l1,
                                    s2 + l2,
                                    len(text2) - s2 - l2,
                                )
                            ],
                        ),
                    )
                return result

            results = []
            for i1 in range(1, l1):  # 空文字の変換は考えないので1以上l1-1以下で回す
                for i2 in range(l2 + 1):
                    # (s1,l1,s2,l2)を2つの部分に分けたときのscore
                    # (s1,i1,s2,i2)と(s1+i1,l1-i1,s2+i2,l2-i2)
                    r1 = dp(s1, i1, s2, i2)
                    score1 = r1[0]
                    part1 = r1[1]

                    if score1 == float("inf"):
                        continue  # scoreが無限のときはスキップ

                    r2 = dp(s1 + i1, l1 - i1, s2 + i2, l2 - i2)
                    score2 = r2[0]
                    part2 = r2[1]

                    if score2 == float("inf"):
                        continue  # scoreが無限のときはスキップ

                    part = part1 + part2  # part2をpart1に結合
                    results.append((score1 + score2, part))

            # resultsが空のときInfinityを返す
            if len(results) == 0:
                result = (float("inf"), [(s1, l1, s2, l2)])
                memo.set(s1, l1, s2, l2, result)
                if s1 + s2 + l1 + l2 == len(text1) + len(text2) and s1 + s2 > 0:
                    memo.set(0, s1, 0, s2, (float("inf"), [(0, s1, 0, s2)]))
                elif s1 + s2 == 0 and l1 + l2 < len(text1) + len(text2):
                    memo.set(
                        s1 + l1,
                        len(text1) - s1 - l1,
                        s2 + l2,
                        len(text2) - s2 - l2,
                        (
                            float("inf"),
                            [
                                (
                                    s1 + l1,
                                    len(text1) - s1 - l1,
                                    s2 + l2,
                                    len(text2) - s2 - l2,
                                )
                            ],
                        ),
                    )
                return result
            else:
                result = min(results, key=lambda v: v[0])
                memo.set(s1, l1, s2, l2, result)
                return result

        result = dp(0, len(text1), 0, len(text2))
        logger.info(f"Correspondence calculation completed with cost: {result[0]}")
        return result

    def allocate(
        self, text1: str, text2: str, convert_func: Callable[[str], str | None]
    ) -> tuple[float, list[tuple[int, int, int, int]]]:
        """
        Public interface for text allocation.

        Args:
            text1: First text to compare
            text2: Second text to compare
            convert_func: Function to convert text1 segments to text2 format

        Returns:
            Tuple of (cost, correspondence_list)
        """
        logger.info("Starting text allocation process")
        try:
            result = self.find_correspondence(text1, text2, convert_func)
            logger.info("Text allocation completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error during text allocation: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.DEBUG)
    allocator = Allocator()

    print(
        allocator.find_correspondence(
            "馴れ初め", "なれそめ", lambda x: {"馴": "な", "初": "そ"}.get(x, x)
        )
    )
