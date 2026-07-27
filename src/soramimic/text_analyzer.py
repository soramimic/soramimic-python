# 移植元: frontend/src/lib/textAnalyzer.js
"""textAnalyzer.js からの移植(ロジック無改変)。

トークン列の読み補完・記号処理・文節付与、および読み↔シラブル↔バリエーション変換。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .character import Character, TokenFormatter
from .english import English
from .kana_to_syllable import (
    KanaToSyllable,
    absorb_small_kana,
    hira_to_kata,
    remove_unnatural_kana_pattern,
)
from .utils import remove_sign

Token = dict[str, Any]

# JS: /^[\u{3000}-\u{301C}\u{30A1}-\u{30F6}\u{30FB}-\u{30FE}]+$/u
_KATAKANA_ONLY_RE = re.compile("^[　-〜ァ-ヶ・-ヾ]+$")


class TextAnalyzer:
    """textAnalyzer.js の TextAnalyzer(character, kanaToSyllable, english, ...)。"""

    def __init__(
        self,
        character: Character,
        kana_to_syllable: KanaToSyllable,
        english: English,
        tokenize_sentenses: Callable[[list[str]], list[list[Token]]],
        get_yomi: Callable[..., Any],
    ) -> None:
        self.character = character
        self.k2s = kana_to_syllable
        self.english = english
        self.tokenize_sentenses = tokenize_sentenses
        self.get_yomi = get_yomi
        self.tf = TokenFormatter()
        self.kanji = character.kanji

    def tokenize_together(self, texts: list[str]) -> list[list[Token]]:
        ap = self.english.apostrophe
        texts = [ap.to_string(v) for v in texts]
        tokens_list = self.tokenize_sentenses(texts)
        return self.format_tokens_list(tokens_list)

    def format_tokens_list(self, tokens_list: list[list[Token]]) -> list[list[Token]]:
        ap = self.english.apostrophe
        for tokens in tokens_list:
            for token in tokens:
                if self.english.is_fullmatch(token["surface_form"]):
                    token["surface_form"] = ap.to_sign(token["surface_form"])
                    # JS原典は if(pronunciation==="*") がコメントアウトされ常に代入
                    token["pronunciation"] = self.english.to_kana(token["surface_form"])

            for token in tokens:
                if token["pronunciation"] == "*" and self.kanji.is_fullmatch(token["surface_form"]):
                    p = self.kanji.to_kana(token["surface_form"])
                    if p:
                        token["pronunciation"] = p

            # pronunciationが*で、surfaceが平仮名/カタカナ/記号のみのとき、カタカナを読みとする
            for token in tokens:
                if token["pronunciation"] != "*":
                    continue
                s = token["surface_form"]
                s = remove_sign(s)
                s = hira_to_kata(s)
                if _KATAKANA_ONLY_RE.match(s):
                    token["pronunciation"] = s

            tokens[:] = self.tf.format(tokens)
            for token in tokens:
                if token["pronunciation"] == "*":
                    token["pos"] = "記号"

            self._absorb_small_kana_in_tokens(tokens)
        return tokens_list

    @staticmethod
    def _absorb_small_kana_in_tokens(tokens: list[Token]) -> None:
        """読みに残った小書きカナ(「ハァ」「ウッセェ」など)を大文字に吸収する。

        単独の小書きはどの単語の発音にも現れない(単語リスト側は format_kana で
        正規化済み)ため、放置すると行全体の候補が0件になる。
        トークンをまたぐ組み合わせ(「シ」+「ェ」)も拾えるよう行単位で連結して正規化する。
        absorb_small_kana は1文字→1文字の置換で長さを変えないので、そのまま
        トークン境界で切り戻せる(surfaceとの位置対応も崩さない)。
        """
        joined = "".join(
            t["pronunciation"] if isinstance(t.get("pronunciation"), str) else "" for t in tokens
        )
        absorbed = absorb_small_kana(joined)
        if absorbed == joined:
            return
        pos = 0
        for token in tokens:
            pron = token.get("pronunciation")
            if not isinstance(pron, str):
                continue
            token["pronunciation"] = absorbed[pos : pos + len(pron)]
            pos += len(pron)

    def get_yomi_from_tokens(self, tokens: list[Token]) -> str:
        yomi = "".join(v["pronunciation"] if v.get("pronunciation") else "" for v in tokens)
        return remove_sign(yomi)

    def format_kana(self, text: str) -> str:
        # 英字の並びは、マッチした部分だけをカナ化して置換する。
        # (以前は text 全体を to_kana した結果で置換しており、英字がk箇所あると
        #  読みが約k+1倍に膨張して後段のバリエーション展開が指数爆発していた)
        text = re.sub(r"[a-zA-Z']+", lambda m: self.english.to_kana(m.group(0)), text)
        text = hira_to_kata(text)
        text = remove_sign(text)
        text = remove_unnatural_kana_pattern(text)
        return text

    @staticmethod
    def _concat_mora(tokens: list[Token]) -> list[Token]:
        for i, token in enumerate(tokens):
            if i == 0:
                continue
            elif token["char_index"] == tokens[i - 1]["char_index"]:
                token["surface_form"] = ""
        mora: list[Token] = []
        last_mora = -1
        for token in tokens:
            if token["mora"] != last_mora:
                last_mora = token["mora"]
                mora.append(token)
            else:
                mora[len(mora) - 1]["surface_form"] += token["surface_form"]
                mora[len(mora) - 1]["pronunciation"] += token["pronunciation"]
        return mora

    def get_yomi_and_phrase_break(self, tokens: list[Token]) -> list[Token]:
        tokens = self.character.tokenize(tokens)
        reduced: list[Token] = []
        for token in tokens:
            obj: Token = {}
            for v in (
                "surface_form",
                "token_index",
                "phrase",
                "pronunciation",
                "subword",
                "char_index",
            ):
                obj[v] = token[v]
            reduced.append(obj)
        tokens = reduced

        subword_kana: list[str] = []
        last_subword = -1
        for token in tokens:
            if token["subword"] != last_subword:
                subword_kana.append(token["pronunciation"])
                last_subword = token["subword"]
            else:
                subword_kana[len(subword_kana) - 1] += token["pronunciation"]

        mora: list[Any] = []
        for v in subword_kana:
            sp = self.k2s.split(v)
            if sp is None:
                mora.append(None)  # JSの .flat() は null 要素を保持する
            else:
                mora.extend(sp)

        mora_index: list[int] = []
        for i, v in enumerate(mora):
            mora_index.extend([i] * len(v))

        for i in range(len(mora_index)):
            tokens[i]["mora"] = mora_index[i]

        tokens = self._concat_mora(tokens)
        return tokens

    def yomi_to_syllable(self, yomi: str) -> list[str] | None:
        return self.k2s.split(yomi)

    def syllable_to_variation(
        self, syllables: list[str] | None, max_units: int | None = None
    ) -> list[list[str]]:
        return self.k2s.get_variation(syllables, max_units)

    def yomi_to_variation(self, yomi: str, max_units: int | None = None) -> list[list[str]]:
        """読みを発音バリエーション(ユニット列)の一覧にする。

        max_units は KanaToSyllable.get_variation と同じ意味(既定 None = 無制限)。
        """
        sep = self.k2s.split(yomi)
        return self.k2s.get_variation(sep, max_units)
