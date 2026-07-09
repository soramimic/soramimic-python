"""同梱サンプル単語リスト(tidy CSV)。

出典は soramimic-wordlists ( https://github.com/soramimic/soramimic-wordlists ) 。
国名・生物名・駅名という事実データのみを同梱している(権利上の配慮から、
キャラクター名・実在人名のリストは同梱しない)。
"""

from __future__ import annotations

from importlib import resources

SAMPLE_WORDLISTS = ("nations", "sekitsui", "stations")


def load_sample_wordlist(name: str) -> str:
    """同梱サンプル単語リストのCSVテキストを返す。

    `word_list.parse_tidy()` にそのまま渡せる。利用できる名前は
    SAMPLE_WORDLISTS を参照(nations=国名, sekitsui=脊椎動物, stations=駅名)。
    """
    if name not in SAMPLE_WORDLISTS:
        raise ValueError(f"unknown sample wordlist: {name!r} (available: {SAMPLE_WORDLISTS})")
    path = resources.files("soramimic.data") / "samples" / f"{name}.csv"
    return path.read_text(encoding="utf-8")
