# 移植元: frontend/src/lib/ruby.js
"""青空文庫ルビ記法(｜表層《よみ》)のパーサ。

記法入りテキストを「素テキスト + 区間注釈」に分解するだけの前処理層で、
類似度計算や DP には一切関与しない。注釈区間の読みは TextAnalyzer 側で
トークンの pronunciation として強制される。

記法(v1は明示形のみ):
    ｜表層《よみ》  … 表層の読みを「よみ」に強制する
    開始記号は ｜(U+FF5C) と |(U+007C) の両方を受理、読み括弧は 《》 のみ
エスケープ(でんでんマークダウン流):
    \\｜ \\| \\《 \\》 \\\\ は文字そのもの。それ以外の文字の前の \\ はそのまま文字
寛容規則:
    - 《よみ》が続かない ｜ は通常文字
    - ｜を伴わない 《…》 は通常文字(暗黙形は未対応)
    - 表層が空・読みが空の記法は無効(全体を通常文字扱い)
    - ｜a｜b《ヨミ》 はネスト不可。後ろの ｜ が有効になり、前の ｜ は通常文字
    - 改行をまたぐ記法は無効
"""

from __future__ import annotations

from typing import Any, NamedTuple

from .kana_to_syllable import hira_to_kata

BARS = frozenset(("｜", "|"))
OPEN = "《"
CLOSE = "》"
# バックスラッシュでエスケープできる文字
ESCAPABLE = frozenset(("｜", "|", "《", "》", "\\"))


class _Atom(NamedTuple):
    kind: str  # "char" | "bar" | "open" | "close"
    ch: str


def _to_atoms(text: str) -> list[_Atom]:
    """テキストをコードポイント単位の「アトム」列にする。

    エスケープはこの段階で解決し、記法文字ではなく通常文字(char)にする。
    """
    atoms: list[_Atom] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            nxt = text[i + 1] if i + 1 < n else None
            if nxt is not None and nxt in ESCAPABLE:
                atoms.append(_Atom("char", nxt))
                i += 2
                continue
            # エスケープ対象外(や行末)の \ はそのまま文字
            atoms.append(_Atom("char", "\\"))
            i += 1
            continue
        if c in BARS:
            atoms.append(_Atom("bar", c))
        elif c == OPEN:
            atoms.append(_Atom("open", c))
        elif c == CLOSE:
            atoms.append(_Atom("close", c))
        else:
            atoms.append(_Atom("char", c))
        i += 1
    return atoms


def _is_newline(ch: str) -> bool:
    return ch in ("\n", "\r")


def _match_ruby(atoms: list[_Atom], i: int) -> tuple[str, str, int] | None:
    """atoms[i] の bar から始まる区間が有効な記法かを調べる。

    表層・読みはともに「通常文字が1個以上・改行を含まない」ことが条件。
    表層の途中に別の bar や 《 が現れた時点で無効(=この bar は通常文字)になるため、
    ｜a｜b《ヨミ》 は自動的に後ろの ｜ が勝つ。
    """
    j = i + 1
    n = len(atoms)
    surface: list[str] = []
    while j < n and atoms[j].kind == "char" and not _is_newline(atoms[j].ch):
        surface.append(atoms[j].ch)
        j += 1
    if not surface:
        return None
    if j >= n or atoms[j].kind != "open":
        return None
    j += 1
    reading: list[str] = []
    while j < n and atoms[j].kind == "char" and not _is_newline(atoms[j].ch):
        reading.append(atoms[j].ch)
        j += 1
    if not reading:
        return None
    if j >= n or atoms[j].kind != "close":
        return None
    return "".join(surface), "".join(reading), j + 1


def parse_ruby(text: str) -> dict[str, Any]:
    """記法入りテキスト → {"plain": str, "annotations": [{start, end, reading}]}。

    plain は記法・エスケープを解決した素テキスト。
    start/end は plain 上のコードポイントオフセット(end は排他)。
    reading はひらがなをカタカナに正規化して格納する。
    """
    atoms = _to_atoms(text if isinstance(text, str) else str(text))
    plain: list[str] = []
    annotations: list[dict[str, Any]] = []
    i = 0
    n = len(atoms)
    while i < n:
        atom = atoms[i]
        if atom.kind == "bar":
            m = _match_ruby(atoms, i)
            if m is not None:
                surface, reading, nxt = m
                start = len(plain)
                plain.extend(surface)
                annotations.append(
                    {"start": start, "end": len(plain), "reading": hira_to_kata(reading)}
                )
                i = nxt
                continue
        plain.append(atom.ch)
        i += 1
    return {"plain": "".join(plain), "annotations": annotations}


def has_ruby(text: str) -> bool:
    """有効な記法を含むか。"""
    return len(parse_ruby(text)["annotations"]) > 0
