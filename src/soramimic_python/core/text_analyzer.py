# -*- coding: utf-8 -*-
from typing import Any, Callable
from .character import TokenFormatter


class TextAnalyzer:
    """
    JS: TextAnalyzer(character, kanaToSyllable, english, tokenizeSentenses, getYomi)
    依存:
        - TokenFormatter(): .format(tokens) を持つ
        - character: .kanji と .tokenize(tokens) を持つ
        - kanaToSyllable: .split(text), .getVariation(syllables) を持つ
        - english: .apostrophe, .isFullmatch(), .toKana() を持つ
        - tokenizeSentenses: list[str] -> list[list[token_dict]]
        - getYomi: str -> str
    """

    def __init__(
        self,
        character,
        kana_to_syllable,
        english,
        tokenize_sentenses: Callable[[list[str]], list[list[dict[str, str]]]],
        get_yomi: Callable[[str], str],
    ):
        self.character = character
        self.k2s = kana_to_syllable
        self.english = english
        self.tokenize_sentenses = tokenize_sentenses
        self.get_yomi_func = get_yomi

        self.tf = TokenFormatter()
        self.kanji = self.character.kanji

    # ひらがなをカタカナに
    @staticmethod
    def hira_to_kata(s: str) -> str:
        return "".join(
            chr(ord(ch) + 0x60) if "\u3041" <= ch <= "\u3096" else ch
            for ch in s
        )

    @staticmethod
    def remove_sign(s: str) -> str:
        # 記号削除用の簡易版（必要に応じて正規表現強化）
        import re
        return re.sub(r"[^\wぁ-ゔァ-ヴー一-龠]", "", s)

    @staticmethod
    def remove_unnatural_kana_pattern(s: str) -> str:
        # 不自然なカナパターンを除去する処理（詳細は実装環境に合わせて調整）
        return s

    def tokenize_together(self, texts: list[str]) -> list[list[dict[str, Any]]]:
        AP = self.english.apostrophe
        texts = [AP.to_string(v) for v in texts]

        tokens_list = self.tokenize_sentenses(texts)
        processed_list = []
        for tokens in tokens_list:
            # 英単語の処理
            for token in tokens:
                if self.english.is_fullmatch(token["surface_form"]):
                    token["surface_form"] = AP.to_sign(token["surface_form"])
                    token["pronunciation"] = self.english.toKana(token["surface_form"])

            # 漢字の処理
            for token in tokens:
                if token["pronunciation"] == "*" and self.kanji.is_fullmatch(token["surface_form"]):
                    p = self.kanji.to_kana(token["surface_form"])
                    if p:
                        token["pronunciation"] = p

            # カタカナ読みの設定
            for token in tokens:
                if token["pronunciation"] != "*":
                    continue
                s = self.remove_sign(token["surface_form"])
                s = self.hira_to_kata(s)
                if all("\u30a1" <= ch <= "\u30f6" or "\u3000" <= ch <= "\u301c" or "\u30fb" <= ch <= "\u30fe" for ch in s):
                    token["pronunciation"] = s

            tokens = self.tf.format(tokens)

            for token in tokens:
                if token["pronunciation"] == "*":
                    token["pos"] = "記号"

            processed_list.append(tokens)

        return processed_list

    def get_yomi_from_tokens(self, tokens: list[dict[str, Any]]) -> str:
        yomi = "".join(token.get("pronunciation", "") for token in tokens)
        return self.remove_sign(yomi)

    def format_kana(self, text: str) -> str:
        import re
        def repl(match):
            return self.english.toKana(match.group(0))

        text = re.sub(r"[a-zA-Z']+", repl, text)
        text = self.hira_to_kata(text)
        text = self.remove_sign(text)
        text = self.remove_unnatural_kana_pattern(text)
        return text

    def concat_mora(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 同じ char_index の surface_form をまとめる
        for i in range(1, len(tokens)):
            if tokens[i]["char_index"] == tokens[i - 1]["char_index"]:
                tokens[i]["surface_form"] = ""
        mora_tokens = []
        last_mora = -1
        for token in tokens:
            if token["mora"] != last_mora:
                last_mora = token["mora"]
                mora_tokens.append(token.copy())
            else:
                mora_tokens[-1]["surface_form"] += token["surface_form"]
                mora_tokens[-1]["pronunciation"] += token["pronunciation"]
        return mora_tokens

    def get_yomi_and_phrase_break(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tokens = self.character.tokenize(tokens)
        tokens = [
            {k: token[k] for k in ["surface_form", "token_index", "phrase", "pronunciation", "subword", "char_index"]}
            for token in tokens
        ]
        # subword -> カナ配列
        subword_kana = []
        last_subword = -1
        for token in tokens:
            if token["subword"] != last_subword:
                subword_kana.append(token["pronunciation"])
                last_subword = token["subword"]
            else:
                subword_kana[-1] += token["pronunciation"]

        mora = [syll for kana in subword_kana for syll in self.k2s.split(kana)]
        mora_index = [i for i, seg in enumerate(mora) for _ in seg]

        for idx, mi in enumerate(mora_index):
            tokens[idx]["mora"] = mi

        tokens = self.concat_mora(tokens)
        return tokens

    def yomi_to_syllable(self, yomi: str) -> list[str]:
        return self.k2s.split(yomi)

    def syllable_to_variation(self, syllables: list[str]) -> list[str]:
        return self.k2s.get_variation(syllables)

    def yomi_to_variation(self, yomi: str) -> list[str]:
        return self.k2s.get_variation(self.k2s.split(yomi))

    def get_yomi(self, text: str) -> str:
        return self.get_yomi_func(text)