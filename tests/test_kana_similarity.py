"""kana_similarity の代表ケースのテスト。"""

from __future__ import annotations

from typing import Any

from soramimic.kana_similarity import KanaSimilarity


def test_get_kana_similarity_structure(default_data: dict[str, Any]) -> None:
    ks = KanaSimilarity(
        default_data["vowel_similarity"],
        default_data["consonant_similarity"],
        default_data["kana2phonon"],
    )
    table = ks.get_kana_similarity({})
    # 全カナ + 伸ばし棒バリアントが対称的に含まれる
    assert "ア" in table and "カ" in table
    assert "カー" in table  # 母音で終わるカナの伸ばし棒バリアント
    assert isinstance(table["ア"]["ア"], float)
    # 各行は全キーを列に持つ(N×N)
    assert set(table["カ"].keys()) == set(table.keys())


def test_set_and_get(default_data: dict[str, Any]) -> None:
    ks = KanaSimilarity(
        default_data["vowel_similarity"],
        default_data["consonant_similarity"],
        default_data["kana2phonon"],
    )
    assert ks.get() is None
    ks.set_kana_similarity({})
    assert ks.get() is not None
    assert "カ" in ks.get()


def test_reward_multiplier_changes_value(default_data: dict[str, Any]) -> None:
    ks = KanaSimilarity(
        default_data["vowel_similarity"],
        default_data["consonant_similarity"],
        default_data["kana2phonon"],
    )
    base = ks.get_kana_similarity({})
    # 同じカナ報酬を変えると対角成分がスケールする
    rewarded = ks.get_kana_similarity({"SAME_KANA_REWARD": 2})
    assert rewarded["カ"]["カ"] == base["カ"]["カ"] * 2
    # 異なるカナ(同子音・同母音でない)は影響を受けない
    assert rewarded["カ"]["ヌ"] == base["カ"]["ヌ"]
