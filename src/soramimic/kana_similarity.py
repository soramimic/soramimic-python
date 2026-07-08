# 移植元: frontend/src/lib/kanaSimilarity.js
"""kanaSimilarity.js からの移植(ロジック無改変)。

子音・母音の類似度テーブルと kana2phonon から、カナ単位の距離テーブルを構築する。
"""

from __future__ import annotations

import copy
from typing import Any

from .kana_to_syllable import (
    create_kana_converter,
    is_same_consonant,
    is_same_hatsuon,
    is_same_kana,
    is_same_sokuon,
    is_same_vowel,
)

SimTable = dict[str, dict[str, float]]


class KanaSimilarity:
    """kanaSimilarity.js の KanaSimilarity()。"""

    def __init__(
        self,
        vowel_similarity: dict[str, dict[str, float]],
        consonant_similarity: dict[str, dict[str, float]],
        kana2phonon: dict[str, Any],
    ) -> None:
        self._kana_converter = create_kana_converter(kana2phonon)
        self._base = self._build_base(vowel_similarity, consonant_similarity, kana2phonon)
        self._kana_similarity: SimTable | None = None

    @staticmethod
    def _build_base(
        vowel_similarity: dict[str, dict[str, float]],
        consonant_similarity: dict[str, dict[str, float]],
        kana2phonon: dict[str, Any],
    ) -> SimTable:
        sims = [consonant_similarity, vowel_similarity]
        k2p = copy.deepcopy(kana2phonon)

        # 伸ばし棒を追加(母音で終わるカナのみ)
        for k1 in list(k2p.keys()):
            has_vowel = k2p[k1][1][-1] in "aiueo"
            if has_vowel:
                k2p[k1 + "ー"] = [k2p[k1][0], k2p[k1][1] + ":"]
        k2plist = list(k2p.keys())

        base: SimTable = {}
        for k1 in k2plist:
            p1 = k2p[k1]
            row: dict[str, float] = {}
            for k2 in k2plist:
                p2 = k2p[k2]
                # 子音同士・母音同士の類似度の平均
                row[k2] = (sims[0][p1[0]][p2[0]] + sims[1][p1[1]][p2[1]]) / 2
            base[k1] = row
        return base

    @staticmethod
    def _assign_default_parameter(parameters: dict[str, Any]) -> dict[str, Any]:
        default_parameter_values: dict[str, Any] = {
            "SAME_PHRASE_BREAK_REWARD": 1,
            "SAME_KANA_REWARD": 1,
            "SAME_VOWEL_REWARD": 1,
            "SAME_CONSONANT_REWARD": 1,
            "SAME_BAR_REWARD": 1,
            "SAME_HATSUON_REWARD": 1,
            "SAME_SOKUON_REWARD": 1,
        }
        default_parameter_values.update(parameters)
        return default_parameter_values

    def get_kana_similarity(self, parameters: dict[str, Any] | None = None) -> SimTable:
        """パラメータに基づいて微調整した類似度テーブルを返す(getKanaSimilarity)。"""
        param = self._assign_default_parameter(parameters or {})
        ksb = self._base
        ksb_keys = list(ksb.keys())

        result: SimTable = {}
        for k1 in ksb_keys:
            row: dict[str, float] = {}
            ksb_k1 = ksb[k1]
            for k2 in ksb_keys:
                s = ksb_k1[k2]
                if is_same_kana(k1, k2):
                    s *= param["SAME_KANA_REWARD"]
                if is_same_vowel(k1, k2):
                    s *= param["SAME_VOWEL_REWARD"]
                if is_same_consonant(k1, k2):
                    s *= param["SAME_CONSONANT_REWARD"]
                if is_same_hatsuon(k1, k2):
                    s *= param["SAME_HATSUON_REWARD"]
                if is_same_sokuon(k1, k2):
                    s *= param["SAME_SOKUON_REWARD"]
                row[k2] = s
            result[k1] = row
        return result

    def set_kana_similarity(self, param: dict[str, Any] | None = None) -> None:
        self._kana_similarity = self.get_kana_similarity(param or {})

    def get(self) -> SimTable | None:
        return self._kana_similarity
