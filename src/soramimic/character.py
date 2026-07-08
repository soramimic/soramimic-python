# 移植元: frontend/src/lib/character.js
"""character.js からの移植(ロジック無改変)。

Kanji(漢字→読みの割当)、Character(表層と発音の文字単位対応)、
TokenFormatter(トークン列の後処理)を提供する。
トークンは可変 dict として扱い、動的にキーが生える(dataclass 化しない)。
"""

from __future__ import annotations

import math
import re
from typing import Any

Token = dict[str, Any]


def _hira_to_kata(s: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        return chr(ord(m.group(0)) + 0x60)

    return re.sub(r"[ぁ-ゖ]", _repl, s)


def _js_number(s: str) -> float:
    """JSの Number(string) の部分的再現(空白trim、空文字は0、非数はNaN)。"""
    t = s.strip()
    if t == "":
        return 0.0
    try:
        return float(t)
    except ValueError:
        return float("nan")


class TokenFormatter:
    """character.js の TokenFormatter()。"""

    @staticmethod
    def _remove_sign_pronunciation(tokens: list[Token]) -> list[Token]:
        for token in tokens:
            if token["pos"] == "記号":
                token["pronunciation"] = token["surface_form"]
        return tokens

    @staticmethod
    def _remove_unknown_sahen(tokens: list[Token]) -> list[Token]:
        for token in tokens:
            if (
                token["pos"] == "名詞"
                and token["pos_detail_1"] == "サ変接続"
                and not token.get("pronunciation")
            ):
                token["pos"] = "記号"
                token["pronunciation"] = ""
        return tokens

    @staticmethod
    def _is_small_kana_start(char: str) -> bool:
        return re.match(r"^[ぁぃぅぇぉゃゅょゎっァィゥェォヮャュョッ]", char) is not None

    @staticmethod
    def _is_kana_end(char: str) -> bool:
        return re.search(r"[ぁ-ゔァ-ヴ]$", char) is not None

    @staticmethod
    def _is_kana(text: str) -> bool:
        return re.match(r"^[ぁ-ゔァ-ヴー]+$", text) is not None

    @classmethod
    def _concat_small_kana(cls, tokens: list[Token]) -> list[Token]:
        for i in range(1, len(tokens)):
            if cls._is_small_kana_start(tokens[i]["surface_form"]) and cls._is_kana_end(
                tokens[i - 1]["surface_form"]
            ):
                tokens[i - 1]["surface_form"] += tokens[i]["surface_form"]
                tokens[i - 1]["pronunciation"] += tokens[i]["pronunciation"]
                tokens[i]["isRemove"] = True
        return [v for v in tokens if not v.get("isRemove")]

    @classmethod
    def _set_kana_pronunciation(cls, tokens: list[Token]) -> list[Token]:
        for token in tokens:
            if cls._is_kana(token["surface_form"]):
                token["pronunciation"] = _hira_to_kata(token["surface_form"])
                if token["pos"] == "記号":
                    token["pos"] = "名詞"
        return tokens

    @staticmethod
    def _concat_single_bar(tokens: list[Token]) -> list[Token]:
        for i in range(1, len(tokens)):
            if tokens[i]["surface_form"] == "ー":
                tokens[i - 1]["surface_form"] += "ー"
                tokens[i - 1]["pronunciation"] += "ー"
        return [token for token in tokens if token["surface_form"] != "ー"]

    @staticmethod
    def _set_number_pronunciation(tokens: list[Token]) -> list[Token]:
        n2p = {
            "1": "イチ",
            "2": "ニ",
            "3": "サン",
            "4": "ヨン",
            "5": "ゴ",
            "6": "ロク",
            "7": "ナナ",
            "8": "ハチ",
            "9": "キュウ",
            "0": "ゼロ",
        }
        for token in tokens:
            if re.match(r"^[0-9]$", token["surface_form"]):
                p = ""
                for v in token["surface_form"]:
                    p += n2p[v]
                token["pronunciation"] = p
        return tokens

    @staticmethod
    def _set_phrase_index(tokens: list[Token]) -> list[Token]:
        cnt = 0
        for index, token in enumerate(tokens):
            if index == 0:
                token["phrase"] = 0
                continue
            if token["pos"] in ("名詞", "動詞", "副詞", "形容詞", "形容動詞", "感動詞"):
                cnt += 1
            token["phrase"] = cnt
        return tokens

    def format(self, tokens: list[Token]) -> list[Token]:
        tokens = self._remove_sign_pronunciation(tokens)
        tokens = self._remove_unknown_sahen(tokens)
        tokens = self._set_number_pronunciation(tokens)
        tokens = self._set_kana_pronunciation(tokens)
        tokens = self._concat_single_bar(tokens)
        tokens = self._concat_small_kana(tokens)
        tokens = self._set_phrase_index(tokens)
        return tokens


class Kanji:
    """character.js の Kanji(dictionary)。"""

    def __init__(self, dictionary: dict[str, list[str]]) -> None:
        self.dictionary = dictionary

    def allocate(self, surface: str, pronunciation: str) -> list[list[str]]:
        return self._kanji_allocate(surface, pronunciation, self.dictionary)

    @staticmethod
    def _kanji_allocate(
        surface: str, pronunciation: str, kanji_dict: dict[str, list[str]]
    ) -> list[list[str]]:
        rest_text = pronunciation
        skipped_char = ""
        output: list[list[str]] = []
        for i in range(len(surface)):
            char = surface[i]
            if char not in kanji_dict:
                skipped_char += char
                continue

            yomi_candidates = kanji_dict[char]  # 長さの降順にソート済みとする
            start = -1
            yomi = ""
            for y in yomi_candidates:
                start = rest_text.find(y)
                if start >= 0:
                    yomi = y
                    break
            # マッチする読みが見つからなければスキップ
            if start == -1:
                skipped_char += char
                continue
            if start > 0:
                if len(output) == 0:
                    if skipped_char != "":
                        output.append([skipped_char, rest_text[0:start]])
                        skipped_char = ""
                        rest_text = rest_text[start:]
                        output.append([char, yomi])
                        rest_text = rest_text[len(yomi) :]
                    else:
                        output.append([char, rest_text[0 : start + len(yomi)]])
                        rest_text = rest_text[start + len(yomi) :]
                else:
                    # JS: skipped_char != 0 (数値0とのゆるい比較)。"" と "0" のときのみ偽
                    if _js_number(skipped_char) != 0.0:
                        output.append([skipped_char, rest_text[0:start]])
                        skipped_char = ""
                        rest_text = rest_text[start:]
                        output.append([char, yomi])
                        rest_text = rest_text[len(yomi) :]
                    else:
                        output[len(output) - 1][1] += rest_text[0:start]
                        rest_text = rest_text[start:]
                        output.append([char, yomi])
                        rest_text = rest_text[len(yomi) :]
            else:
                output.append([char, yomi])
                rest_text = rest_text[len(yomi) :]

        # ループで処理しきれなかった文字列の処理
        if skipped_char != "":
            if rest_text != "":
                output.append([skipped_char, rest_text])
            else:
                if len(output) == 0:
                    output.append([skipped_char, rest_text])
                else:
                    output[len(output) - 1][0] += skipped_char
        else:
            if rest_text != "":
                if len(output) == 0:
                    pass  # この分岐はたぶんない
                else:
                    output[len(output) - 1][1] += rest_text
        return output

    @staticmethod
    def is_fullmatch(text: str) -> bool:
        return re.match(r"^[一-龠]+$", text) is not None

    def to_kana(self, text: str) -> str:
        kana = ""
        for i in range(len(text)):
            if text[i] not in self.dictionary:
                continue
            kana += self.dictionary[text[i]][0]
        return kana


class Character:
    """character.js の Character(kanji)。"""

    def __init__(self, kanji: Kanji) -> None:
        self.kanji = kanji

    @staticmethod
    def _kana_tokenize(text: str) -> list[Token]:
        if text == "":
            return []
        re_pat = re.compile(
            r"(?P<kata>[ァ-ヴー]+)|(?P<hira>[ぁ-ゔー]+)|(?P<nonkana>[^ぁ-ゔァ-ヴー]+)"
        )
        output: list[Token] = []
        for m in re_pat.finditer(text):
            groups = m.groupdict()
            token: Token = {}
            for type_ in ("kata", "hira", "nonkana"):
                if groups[type_]:
                    token = {"surface_form": groups[type_], "type": type_}
                    break
            output.append(token)
        return output

    @staticmethod
    def _kana_allocate(separated_surface: list[Token], pronunciation: str) -> list[Token]:
        if len(separated_surface) == 0:
            return []

        first_kana_index = 1
        if separated_surface[0]["type"] != "nonkana":
            first_kana_index = 0
        _first_nonkana_index = 1 - first_kana_index  # noqa: F841 (JS互換のため保持)

        output: list[Token] = []
        rest_text = pronunciation

        for i in range(len(separated_surface)):
            type_ = separated_surface[i]["type"]
            surface = separated_surface[i]["surface_form"]

            if type_ == "nonkana":
                continue

            katakana = surface
            if type_ == "hira":
                katakana = _hira_to_kata(surface)

            start = rest_text.find(katakana)
            # カナ部分の始まりが途中からなら、始めのカナ以外の部分を先に格納
            if start > 0:
                nonkana = separated_surface[i - 1]
                output.append(
                    {
                        "surface_form": nonkana["surface_form"],
                        "pronunciation": rest_text[0 : start - len(rest_text)],
                        "type": nonkana["type"],
                    }
                )
                rest_text = rest_text[start:]
            output.append(
                {
                    "surface_form": surface,
                    "pronunciation": rest_text[0 : len(katakana)],
                    "type": type_,
                }
            )
            rest_text = rest_text[len(katakana) :]
        if rest_text != "":
            last = separated_surface[len(separated_surface) - 1]
            last_surface = last["surface_form"] if last["type"] == "nonkana" else ""
            output.append(
                {"surface_form": last_surface, "pronunciation": rest_text, "type": last["type"]}
            )
        return output

    @staticmethod
    def balanced_allocate(surface: str, pronunciation: str) -> list[Token]:
        id_ = {"surface_form": "surface_form", "pronunciation": "pronunciation"}
        text = {"surface_form": surface, "pronunciation": pronunciation}
        longer = id_["surface_form"]
        shorter = id_["pronunciation"]
        if len(surface) <= len(pronunciation):
            longer = id_["pronunciation"]
            shorter = id_["surface_form"]

        shorter_len = len(text[shorter])
        longer_len = len(text[longer])
        if shorter_len == 0:
            # JSでは 0除算により Infinity/NaN となりループが回らず [] を返す
            return []
        plusone = longer_len % shorter_len
        contentlen = math.floor(longer_len / shorter_len)

        output: list[Token] = []
        longer_pos = 0
        for i in range(shorter_len):
            longer_content_len = contentlen
            if i < plusone:
                longer_content_len += 1
            if longer == id_["pronunciation"]:
                for j in range(longer_content_len):
                    info: Token = {}
                    info[longer] = text[longer][longer_pos + j]
                    info[shorter] = text[shorter][i]
                    info["in_surface_pos"] = j
                    output.append(info)
                longer_pos += longer_content_len
            else:
                info = {}
                info[longer] = text[longer][longer_pos : longer_pos + longer_content_len]
                info[shorter] = text[shorter][i]
                info["in_surface_pos"] = 0
                longer_pos += longer_content_len
                output.append(info)
        return output

    @staticmethod
    def _concat_sign_token(tokens: list[Token]) -> list[Token]:
        formatted: list[Token] = []
        for token in tokens:
            if token.get("type") == "sign":
                if len(formatted) > 0:
                    formatted[len(formatted) - 1]["surface_form"] += token["surface_form"]
                continue
            else:
                formatted.append(token)
        return formatted

    def _get_char_correspondance(self, tokens: list[Token], kanji_allocator: Kanji) -> list[Token]:
        # token(単語)のidをふる
        for index, token in enumerate(tokens):
            token["token_index"] = index

        # カナ部分とカナ以外部分の対応を見つける
        kana_correspondance_nested: list[list[Token]] = []
        for token in tokens:
            if not token.get("pronunciation"):
                token["pronunciation"] = ""
            separated = self._kana_tokenize(token["surface_form"])
            correspondance = self._kana_allocate(separated, token["pronunciation"])
            if token["pos"] == "記号":
                for v in correspondance:
                    v["type"] = "sign"
            for v in correspondance:
                for k in token:
                    if k not in v:
                        v[k] = token[k]
            kana_correspondance_nested.append(correspondance)
        kana_correspondance: list[Token] = [v for sub in kana_correspondance_nested for v in sub]

        # 1文字ずつの対応を見つける
        subword_index = -1
        char_correspondance_nested: list[list[Token]] = []
        for token in kana_correspondance:
            if (
                token["type"] == "nonkana"
                and len(token["surface_form"]) > 1
                and re.match(r"^[A-Za-z0-9_']+$", token["surface_form"]) is None
            ):
                pairs = kanji_allocator.allocate(token["surface_form"], token["pronunciation"])
                correspondance_nested: list[list[Token]] = []
                for surface_form, yomi in pairs:
                    c = self.balanced_allocate(surface_form, yomi)
                    if len(surface_form) == 1:
                        pass
                    else:
                        # 小さい文字から読みが始まるsurfaceがあれば修正する
                        for i in range(len(c)):
                            v = c[i]
                            if (
                                re.match(r"^[ァィゥェォヮャュョ]", v["pronunciation"])
                                and v["in_surface_pos"] == 0
                                and i > 0
                            ):
                                for j in range(i - 1, len(c)):
                                    if j >= i - 1 + 2 and c[j]["in_surface_pos"] == 0:
                                        break
                                    c[j]["in_surface_pos"] = j - i + 1
                                    c[j]["surface_form"] = v["surface_form"]
                    subword_index += 1
                    for i in range(len(c)):
                        c[i]["subword"] = subword_index
                    correspondance_nested.append(c)
                correspondance = [v for sub in correspondance_nested for v in sub]
            else:
                surf_is_kana_or_empty = token["surface_form"] == "" or (
                    re.match(r"^[ぁ-ゔァ-ヴー]+$", token["surface_form"]) is not None
                )
                if surf_is_kana_or_empty and len(token["surface_form"]) != len(
                    token["pronunciation"]
                ):
                    correspondance = [
                        {
                            "surface_form": token["surface_form"][i]
                            if i < len(token["surface_form"])
                            else "",
                            "pronunciation": p,
                            "in_surface_pos": 0,
                        }
                        for i, p in enumerate(token["pronunciation"])
                    ]
                else:
                    correspondance = self.balanced_allocate(
                        token["surface_form"], token["pronunciation"]
                    )
                subword_index += 1
                for i in range(len(correspondance)):
                    correspondance[i]["subword"] = subword_index

            for v in correspondance:
                for k in token:
                    if k in v:
                        continue
                    v[k] = token[k]
            char_correspondance_nested.append(correspondance)
        char_correspondance: list[Token] = [v for sub in char_correspondance_nested for v in sub]

        # surfaceのindexを付与
        index_c = -1
        for token in char_correspondance:
            in_surface_pos = token["in_surface_pos"]
            if in_surface_pos == 0:
                index_c += 1
            token["char_index"] = index_c

        char_correspondance = self._concat_sign_token(char_correspondance)
        return char_correspondance

    def tokenize(self, tokens: list[Token]) -> list[Token]:
        return self._get_char_correspondance(tokens, self.kanji)
