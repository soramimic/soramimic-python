"""Reading-provider boundary for word lists."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

ReadingResolver = Callable[[str], str]
_KANA = re.compile(r"[ァ-ヺー]+")


def resolve_wordlist_reading(text: str, resolver: ReadingResolver) -> str:
    """Resolve every input, including explicit readings, and require nonempty kana.

    Normalize width before the provider sees Latin letters or numbers. Providers
    such as soramimic_yomi.get_yomi can be supplied without a core dependency.
    """
    result = resolver(unicodedata.normalize("NFKC", text).strip())
    if not isinstance(result, str):
        raise ValueError("読み推定の結果が文字列ではありません。読みをカナで指定してください。")
    result = unicodedata.normalize("NFKC", result)
    result = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in result)
    if not _KANA.fullmatch(result):
        invalid = "".join(dict.fromkeys(re.sub(r"[ァ-ヺー]", "", result)))
        reason = f"使えない文字「{invalid}」が残っています" if result else "読みが空になりました"
        raise ValueError(
            f"入力「{text}」の読み「{result}」: {reason}。正しい読みをカナで指定してください。"
        )
    return result
