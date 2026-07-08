import re
import regex
from collections.abc import Callable
from typing import Any, TypedDict

import jaconv
import neologdn

from soramimic_python.core.character import TokenFormatter, RubiAligner, join_silent_pairs, Kanji
from soramimic_python.core.mecab_tokenizer import split_to_phrases, MecabToken
from soramimic_python.core.english import English

class Mora(TypedDict):
    surface: str
    pronunciation: str
    is_phrase_start: bool

rubi_aligner = RubiAligner()
english = English()
kanji = Kanji()


def split_chunks(text: str):
    """
    カナ（ひらがな+カタカナ）、数字、アルファベット、漢字の塊を
    入力順に [(種類, 文字列), ...] で返す。
    「ヶ」「ヵ」は常に漢字扱い。
    """
    pattern = regex.compile(
        r'(?P<kanji>(?:\p{Han}|ヶ|ヵ)+)|'         # 漢字 + 「ヶ」「ヵ」
        r'(?P<number>\p{Nd}+)|'                   # 十進数字（全角含む）
        r'(?P<alpha>\p{Latin}+)|'                 # ラテン文字（全角含む）
        r'(?P<kana>\p{Katakana_Or_Hiragana}+)'    # ひらがな・カタカナ
    )
    out = []
    for m in pattern.finditer(text):
        for k, v in m.groupdict().items():
            if v:
                out.append((k, v))
                break
    return out

def _convert_surface_to_pronunciation(surface: str) -> str:
    surface = neologdn.normalize(surface)
    chunks = split_text_chunks_with_type(surface)
    pronunciation = ""
    for chunk_type, chunk_value in chunks:
        if chunk_type == "kana":
            # ひらがな・カタカナはそのまま
            pronunciation += jaconv.hira2kata(chunk_value)
        elif chunk_type == "number":
            # 数字はそのまま
            pronunciation += chunk_value
        elif chunk_type == "alpha":
            # アルファベットは英語変換
            pronunciation += english._english_to_kana(chunk_value)
        elif chunk_type == "kanji":
            # 漢字は読みを取得
            pronunciation += kanji.to_kana(chunk_value)
    return pronunciation

def tokenize(text: str) -> list[Mora]:
    ap = english.apostrophe
    phrases = split_to_phrases(text)
    moras = []
    for phrase in phrases:
        phrase_pairs = []
        for token in phrase:
            # アポストロフィを戻す
            token["surface"] = ap.to_sign(token["surface"])
            # 記号ではなく発音が未定義であれば、surfaceから発音を取得
            if token["pos"] != "記号" and token["pronunciation"] and token["pronunciation"] != "*":
                pass
            else:
                token["pronunciation"] = _convert_surface_to_pronunciation(token["surface"])
            # surfaceとpronunciationをなるべく細かく対応付け
            pairs = rubi_aligner.align(token["surface"], token["pronunciation"])
            phrase_pairs.extend(pairs)
        # pronunciationがないtokenを前後と結合する
        phrase_pairs = join_silent_pairs(phrase_pairs)
        phrase_moras = []
        for phrase_pair in phrase_pairs:
            word_pairs = []
            for p in phrase_pair["pronunciation"]:
                mora = {
                    "surface": "",
                    "pronunciation": p,
                    "is_phrase_start": False
                }
                word_pairs.append(mora)
            word_pairs[0]["surface"] = phrase_pair["surface"]
            phrase_moras.extend(word_pairs)
        phrase_moras[0]["is_phrase_start"] = True
        moras.extend(phrase_moras)
    return moras

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
    ):
        self.character = character
        self.k2s = kana_to_syllable
        self.english = english

        self.tf = TokenFormatter()
        self.kanji = self.character.kanji

    # ひらがなをカタカナに
    @staticmethod
    def _hira_to_kata(s: str) -> str:
        return jaconv.hira2kata(s)

    @staticmethod
    def _remove_sign(s: str) -> str:
        # 記号削除用の簡易版（必要に応じて正規表現強化）
        return re.sub(r"[^\wぁ-ゔァ-ヴー一-龠]", "", s)

    @staticmethod
    def _remove_unnatural_kana_pattern(s: str) -> str:
        # 不自然なカナパターンを除去する処理（詳細は実装環境に合わせて調整）
        return s

    def _convert_surface_to_pronunciation(self, surface: str) -> str:
        # 表層形から発音を取得する処理
        if self.english.is_fullmatch(surface):
            return self.english.to_kana(surface)
        elif self.kanji._is_fullmatch(surface):
            return self.kanji.to_kana(surface)
        else:
            pronunciation = self._hira_to_kata(surface)
            # カタカナのみ抽出
            pronunciation = re.sub(r"[^ァ-ヶー]", "", pronunciation)
            return pronunciation

    def tokenize_together(self, texts: list[str]) -> list[list[MecabToken]]:
        AP = self.english.apostrophe
        texts = [AP.to_string(v) for v in texts]
        phrases_list = []
        for text in texts:
            phrases = tokenize(text)
            for phrase in phrases:
                for token in phrase:
                    token.surface = AP.to_sign(token.surface)
            phrases_list.append(phrases)
    
        for phrases in phrases_list:
            for phrase in phrases:
                for token in phrase:
                    if token.pos != "記号" and token.pronunciation and token.pronunciation != "*":
                        pass
                    else:
                        token.pronunciation = self._convert_surface_to_pronunciation(token.surface)

        return phrases_list

    def get_yomi_from_tokens(self, tokens: list[MecabToken]) -> str:
        yomi = "".join(token.get("pronunciation", "") for token in tokens)
        return self._remove_sign(yomi)

    def format_kana(self, text: str) -> str:
        def repl(match):
            return self.english.to_kana(match.group(0))

        text = re.sub(r"[a-zA-Z']+", repl, text)
        text = self._hira_to_kata(text)
        text = self._remove_sign(text)
        text = self._remove_unnatural_kana_pattern(text)
        return text

    def _concat_mora(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    def tokenize(self, text: str) -> list[Mora]:
        tokens = self

    def get_yomi_and_phrase_break(
        self, tokens: list[MecabToken]
    ) -> list[MecabToken]:
        tokens = self.character.tokenize(tokens)
        tokens = [
            {
                k: token[k]
                for k in [
                    "surface_form",
                    "token_index",
                    "phrase",
                    "pronunciation",
                    "subword",
                    "char_index",
                ]
            }
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

        tokens = self._concat_mora(tokens)
        return tokens

    def _yomi_to_syllable(self, yomi: str) -> list[str]:
        return self.k2s.split(yomi)

    def syllable_to_variation(self, syllables: list[str]) -> list[str]:
        return self.k2s.get_variation(syllables)

    def yomi_to_variation(self, yomi: str) -> list[str]:
        return self.k2s.get_variation(self._yomi_to_syllable(yomi))

    def get_yomi(self, text: str) -> str:
        return self.get_yomi_func(text)

if __name__ == "__main__":
    print(tokenize("テスト"))
    print(tokenize("「庭」には二羽鶏がいる。englishを信じて。"))