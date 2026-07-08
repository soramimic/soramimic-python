# fugashi(ipadic)ベースのトークナイザ実装。
"""fugashi + ipadic による MeCab トークナイザ。

kuromojiTokenizer.js / mecabTokenizer.js と同じ正規化を行う:
- 未知語で欠落する reading / pronunciation / basic_form は "*" にする
- ipadic の feature 並び(品詞,品詞細分類1..3,活用型,活用形,原形,読み,発音)を
  トークン dict へマップする。発音・読みが無い(feature が 7 要素以下の)未知語は "*"
- get_yomi は既知語=読み、未知語=表層を連結する(MeCab -Oyomi 相当)
- tokenize / get_yomi とも、リストを渡すとリストで返す

fugashi/ipadic 未導入環境では import 時に分かりやすい ImportError を出す。
"""

from __future__ import annotations

from typing import Any

try:
    import fugashi
    import ipadic
except ImportError as e:  # pragma: no cover - 環境依存
    raise ImportError(
        "MeCabTokenizer は fugashi と ipadic を必要とします。"
        "`pip install 'soramimic[mecab]'` または `uv sync --extra mecab` で導入してください。"
    ) from e

Token = dict[str, Any]


class MeCabTokenizer:
    """fugashi(ipadic)ベースのトークナイザ。"""

    def __init__(self) -> None:
        self._tagger = fugashi.GenericTagger(ipadic.MECAB_ARGS)

    @staticmethod
    def _feature_list(word: Any) -> list[str]:
        raw = getattr(word, "feature_raw", None)
        if raw is not None:
            return list(raw.split(","))
        return [str(x) for x in word.feature]

    def _tokenize_one(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        for j, word in enumerate(self._tagger(text)):
            features = self._feature_list(word)

            def g(idx: int, features: list[str] = features) -> str:
                return features[idx] if idx < len(features) else "*"

            if len(features) > 7:
                basic_form = g(6)
                reading = g(7)
                pronunciation = g(8)
            else:
                basic_form = "*"
                reading = "*"
                pronunciation = "*"

            tokens.append(
                {
                    "surface_form": word.surface,
                    "basic_form": basic_form,
                    "reading": reading,
                    "pronunciation": pronunciation,
                    "pos": g(0),
                    "pos_detail_1": g(1),
                    "pos_detail_2": g(2),
                    "pos_detail_3": g(3),
                    "conjugated_form": g(5),
                    "conjugated_type": g(4),
                    "word_position": j + 1,
                }
            )
        return tokens

    def _yomi_one(self, text: str) -> str:
        parts: list[str] = []
        for word in self._tagger(text):
            features = self._feature_list(word)
            reading = features[7] if len(features) > 7 else "*"
            if reading and reading != "*":
                parts.append(reading)
            else:
                parts.append(word.surface)
        return "".join(parts)

    def tokenize(self, text: str | list[str]) -> list[Token] | list[list[Token]]:
        if isinstance(text, list):
            return [self._tokenize_one(t) for t in text]
        return self._tokenize_one(text)

    def get_yomi(self, text: str | list[str]) -> str | list[str]:
        if isinstance(text, list):
            return [self._yomi_one(t) for t in text]
        return self._yomi_one(text)
