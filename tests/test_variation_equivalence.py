"""get_variation の最適化が結果を変えないことを検証する。

- `_reference_get_variation` は最適化前(直積を全部作ってから平坦化する)実装の
  逐語コピー。これと新実装の出力(ユニット列・vcost・src・並び順)が一致することを
  実データ由来のコーパスで確認する。
- `max_units` を付けた出力が「無制限の出力を長さでフィルタしたもの」と一致すること
  (=枝刈りが結果を変えないこと)も確認する。
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from soramimic import load_sample_wordlist
from soramimic.kana_to_syllable import KanaToSyllable, Variation
from soramimic.utils import product
from soramimic.word_list import WordList


def _reference_get_variation(syllables: list[str] | None) -> list[list[str]]:
    """最適化前の get_variation(kanaToSyllable.js の getVariation 逐語移植)。"""
    result: list[list[dict[str, Any]]] = []
    src_index: list[int] = []
    if not syllables:
        return []
    for syllable_index, syllable in enumerate(syllables):
        if syllable is None:
            continue
        variation: list[dict[str, Any]] = []
        if re.match(r"^[アイウエオ]$", syllable):
            variation.append({"u": [syllable], "c": 0})
        elif re.match(r"^[ンッ]$", syllable):
            variation.append({"u": [syllable], "c": 0})
            variation.append({"u": [""], "c": 1})
        elif syllable == "ンー":
            variation.append({"u": ["ン", "ン"], "c": 1})
            variation.append({"u": ["ン"], "c": 1})
            variation.append({"u": [""], "c": 2})
        elif syllable == "ンッ":
            variation.append({"u": ["ン", "ッ"], "c": 0})
            variation.append({"u": ["ン"], "c": 1})
            variation.append({"u": ["ッ"], "c": 1})
            variation.append({"u": [""], "c": 2})
        elif syllable.endswith("ーン"):
            head = syllable[:-2]
            variation.append({"u": [head + "ー", "ン"], "c": 0})
            variation.append({"u": [head + "ー"], "c": 1})
        elif syllable.endswith("ンッ"):
            head = syllable[:-2]
            variation.append({"u": [head, "ン", "ッ"], "c": 0})
            variation.append({"u": [head, "ン"], "c": 1})
            variation.append({"u": [head + "ー", "ッ"], "c": 1})
            variation.append({"u": [head + "ー"], "c": 2})
            variation.append({"u": [head, "ッ"], "c": 1})
        elif syllable.endswith("ーッ"):
            head = syllable[:-2]
            variation.append({"u": [head + "ー", "ッ"], "c": 0})
            variation.append({"u": [head + "ー"], "c": 1})
        elif syllable.endswith("ー"):
            head = syllable[:-1]
            variation.append({"u": [head + "ー"], "c": 0})
        elif syllable.endswith("ッ"):
            head = syllable[:-1]
            variation.append({"u": [head, "ッ"], "c": 0})
            variation.append({"u": [head], "c": 1})
            variation.append({"u": [head + "ー"], "c": 1})
        elif syllable.endswith("ン"):
            head = syllable[:-1]
            variation.append({"u": [head, "ン"], "c": 0})
            variation.append({"u": [head + "ー"], "c": 1})
            variation.append({"u": [head], "c": 1})
        elif re.search(r"[アイウエオ]$", syllable):
            head = syllable[:-1]
            vowel = syllable[len(syllable) - 1]
            variation.append({"u": [head, vowel], "c": 0})
            variation.append({"u": [head + "ー"], "c": 0})
        else:
            variation.append({"u": [syllable], "c": 0})
        result.append(variation)
        src_index.append(syllable_index)

    out: list[list[str]] = []
    for combo in product(*result):
        flat = Variation(x for e in combo for x in e["u"] if x != "")
        if len(flat) != 0:
            flat.vcost = sum(e["c"] for e in combo)
            flat.src = [src_index[j] for j, e in enumerate(combo) for x in e["u"] if x != ""]
            out.append(flat)
    return out


def _dump(variations: list[list[str]]) -> list[tuple[list[str], int, list[int]]]:
    """比較しやすいよう (ユニット列, vcost, src) のタプル列にする。"""
    return [(list(v), getattr(v, "vcost", 0), list(getattr(v, "src", []))) for v in variations]


#: 分岐を一通り踏む手書きケース(裸ン/ッ・ンー・ンッ・ーン・アンッ・ーッ・長音・母音連続)
HANDMADE = [
    "ン",
    "ッ",
    "ンー",
    "ンッ",
    "アーン",
    "アンッ",
    "アーッ",
    "カー",
    "カア",
    "カン",
    "カッ",
    "トーキョー",
    "シンジュク",
    "サンヨウチョウチンアンコウ",
    "ホワイトスポッテッドウェッジフィッシュ",
    "コンピューター",
    "ファイト",
    "アイウエオ",
]


@pytest.fixture(scope="module")
def corpus(pieces: dict[str, Any]) -> list[str]:
    """同梱サンプル単語リスト由来の読みコーパス(手書きケース込み)。"""
    ta = pieces["text_analyzer"]
    yomi = list(HANDMADE)
    for name, step in (("nations", 1), ("sekitsui", 37), ("stations", 53)):
        lines = load_sample_wordlist(name).splitlines()
        header = lines[0].split(",")
        s_idx = header.index("surface")
        p_idx = header.index("pronunciation") if "pronunciation" in header else None
        for line in lines[1::step]:
            cells = line.split(",")
            if len(cells) <= s_idx:
                continue
            p = cells[p_idx] if p_idx is not None and p_idx < len(cells) else None
            if not p or p in ("NA", "na"):
                p = cells[s_idx]
            if re.search(r"[一-龠]", p):
                continue  # 漢字はトークナイザ依存なので除く
            formatted = ta.format_kana(p)
            if formatted:
                yomi.append(formatted)
    return yomi


def test_matches_reference_implementation(corpus: list[str]) -> None:
    """最適化前の実装と、ユニット列・vcost・src・並び順まで一致する。"""
    k2s = KanaToSyllable()
    checked = 0
    for y in corpus:
        syllables = k2s.split(y)
        if syllables is None or len(syllables) > 14:
            continue  # 参照実装は指数的に遅いので長すぎる読みは別テストで扱う
        assert _dump(k2s.get_variation(syllables)) == _dump(_reference_get_variation(syllables)), y
        checked += 1
    assert checked > 500


def test_none_syllables_are_skipped_like_reference() -> None:
    """None 混じり(split が None を返した行)の扱いも参照実装と同じ。"""
    k2s = KanaToSyllable()
    syllables = ["カン", None, "コ"]  # type: ignore[list-item]
    assert _dump(k2s.get_variation(syllables)) == _dump(_reference_get_variation(syllables))
    assert k2s.get_variation([]) == []
    assert k2s.get_variation(None) == []


def test_max_units_equals_filtering_full_output(corpus: list[str]) -> None:
    """max_units 付きの出力は、無制限出力を長さで絞ったものと完全に一致する。"""
    k2s = KanaToSyllable()
    for y in corpus[:400]:
        syllables = k2s.split(y)
        if syllables is None or len(syllables) > 14:
            continue
        full = k2s.get_variation(syllables)
        for limit in (0, 1, 2, 3, 5, 8, 30):
            expected = [v for v in full if len(v) <= limit]
            assert _dump(k2s.get_variation(syllables, limit)) == _dump(expected), (y, limit)


def test_max_units_prunes_pathological_word() -> None:
    """変種が指数爆発する長い読みでも、上限を指定すれば即座に返る。"""
    k2s = KanaToSyllable()
    # format_kana のJS由来バグ(英字複数語で読みが繰り返される)で生じる長さの読み
    yomi = "レディーティーエイチロアテディーラインボダブリューエスキンケイアカノドニジトカゲ" * 3
    syllables = k2s.split(yomi)
    assert syllables is not None and len(syllables) > 80
    assert k2s.get_variation(syllables, 30) == []  # 最短でも30ユニットを超えるので0件


def test_parse_tidy_max_units_equals_filtered_db(pieces: dict[str, Any]) -> None:
    """parse_tidy(max_units=k) は、無制限DBから長さk以下のバケットを取ったものと同じ。"""
    wl: WordList = pieces["word_list"]
    csv = "\n".join(
        [
            "id,original,surface,pronunciation",
            "1,カンコー,カンコー,カンコー",
            "2,アンコウ,アンコウ,アンコウ",
            "3,サンヨウチョウチンアンコウ,サンヨウチョウチンアンコウ,サンヨウチョウチンアンコウ",
            "4,ア,ア,ア",
        ]
    )
    full = wl.parse_tidy(csv, "")
    for limit in (1, 2, 4, 6, 100):
        limited = wl.parse_tidy(csv, "", limit)
        expected = {k: v for k, v in full.items() if k <= limit}
        assert limited == expected, limit
        assert all(
            w["vcost"] == e["vcost"]
            for k in limited
            for w, e in zip(limited[k], expected[k], strict=True)
        )
