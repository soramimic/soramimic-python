"""
カナ類似度計算モジュール
"""

import copy
import logging

from soramimic_python.core.kana_to_syllable import KanaConverter
logger = logging.getLogger(__name__)




class KanaSimilarity:
    """カナ類似度計算クラス"""

    def __init__(
        self,
        vowel_similarity: dict[str, dict[str, float]],
        consonant_similarity: dict[str, dict[str, float]],
        kana2phonon: dict[str, list[str]],
    ):
        """
        初期化

        Args:
            vowel_similarity: 母音類似度辞書
            consonant_similarity: 子音類似度辞書
            kana2phonon: カナ→音韻辞書
        """
        self.vowel_similarity = vowel_similarity
        self.consonant_similarity = consonant_similarity
        self.kana2phonon = kana2phonon
        self._kana_similarity_base = self._create_kana_similarity_base()
        self._kana_similarity: dict[str, dict[str, float]] | None = None

    def _create_kana_similarity_base(self) -> dict[str, dict[str, float]]:
        """kanaの距離を計算の元を出力する関数"""
        logger.info("Creating kana similarity base")

        sims = [self.consonant_similarity, self.vowel_similarity]
        k2p = copy.deepcopy(self.kana2phonon)

        # 伸ばし棒を追加
        for k1 in list(k2p.keys()):
            if len(k2p[k1]) >= 2:
                has_vowel = k2p[k1][1][-1] in "aiueo"
                if has_vowel:
                    k2p[k1 + "ー"] = [k2p[k1][0], k2p[k1][1] + ":"]

        k2p_list = list(k2p.keys())
        similarity_base = {}

        for k1 in k2p_list:
            p1 = k2p[k1]  # k1のphonon
            similarity_base[k1] = {}

            for k2 in k2p_list:
                p2 = k2p[k2]  # k2のphonon

                # デバッグ用
                if len(p1) >= 2 and p1[1] not in sims[1]:
                    logger.warning(f"k1,p1: {k1}, {p1}")

                # 子音同士、母音同士の類似度の平均をk1とk2の類似度のベースとして定義
                if len(p1) >= 2 and len(p2) >= 2:
                    consonant_sim = sims[0].get(p1[0], {}).get(p2[0], 0.0)
                    vowel_sim = sims[1].get(p1[1], {}).get(p2[1], 0.0)
                    similarity_base[k1][k2] = (consonant_sim + vowel_sim) / 2
                else:
                    similarity_base[k1][k2] = 0.0

        return similarity_base

    def _assign_default_parameter(
        self, parameters: dict[str, float] | None
    ) -> dict[str, float]:
        """parametersに存在しないkeyをDEFAULT_PARAMETER_VALUESで埋めて返す"""
        default_parameter_values = {
            "SAME_PHRASE_BREAK_REWARD": 1.0,  # 文節が一致しているとき掛け算する
            "SAME_KANA_REWARD": 1.0,  # 同じカナに対して掛け算する
            "SAME_VOWEL_REWARD": 1.0,  # 同じ母音に対して掛け算する
            "SAME_CONSONANT_REWARD": 1.0,  # 同じ子音に対して掛け算する
            "SAME_BAR_REWARD": 1.0,  # 拗音同士に対して掛け算する
            "SAME_HATSUON_REWARD": 1.0,  # 撥音同士に対して掛け算する
            "SAME_SOKUON_REWARD": 1.0,  # 促音同士に対して掛け算する
        }

        if parameters is None:
            parameters = {}

        result = default_parameter_values.copy()
        result.update(parameters)
        return result

    def get_kana_similarity(
        self, parameters: dict[str, float] | None = None
    ) -> dict[str, dict[str, float]]:
        """パラメータに基づいて微調整する"""
        param = self._assign_default_parameter(parameters)
        ksb = self._kana_similarity_base
        ksb_keys = list(ksb.keys())

        kana_similarity = {}

        for k1 in ksb_keys:
            kana_similarity[k1] = {}

            for k2 in ksb_keys:
                s = ksb[k1][k2]  # baseのsimilarityを取得

                if KanaConverter.is_same_kana(k1, k2):
                    s *= param["SAME_KANA_REWARD"]
                if KanaConverter.is_same_vowel(k1, k2):
                    s *= param["SAME_VOWEL_REWARD"]
                if KanaConverter.is_same_consonant(k1, k2):
                    s *= param["SAME_CONSONANT_REWARD"]
                if KanaConverter.is_same_hatsuon(k1, k2):
                    s *= param["SAME_HATSUON_REWARD"]
                if KanaConverter.is_same_sokuon(k1, k2):
                    s *= param["SAME_SOKUON_REWARD"]

                kana_similarity[k1][k2] = s

        logger.info(f"getKanaSimilarity: parameters={parameters}, param={param}")
        return kana_similarity

    def set_kana_similarity(self, param: dict[str, float] | None = None) -> None:
        """カナ類似度を設定"""
        logger.info(f"set param: {param}")
        self._kana_similarity = self.get_kana_similarity(param)

    def get(self) -> dict[str, dict[str, float]] | None:
        """設定済みのカナ類似度を取得"""
        return self._kana_similarity
