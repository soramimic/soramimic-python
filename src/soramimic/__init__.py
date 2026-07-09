"""soramimic — 空耳(替え歌)歌詞生成エンジン。

soramimic/soramimic の frontend/src/lib (JS) と挙動互換の Python 移植。
"""

from .factory import Soramimic, create_soramimic, load_default_data
from .samples import SAMPLE_WORDLISTS, load_sample_wordlist
from .tokenizer import Tokenizer

__version__ = "0.1.1"

__all__ = [
    "SAMPLE_WORDLISTS",
    "Soramimic",
    "Tokenizer",
    "create_soramimic",
    "load_default_data",
    "load_sample_wordlist",
    "__version__",
]
