import re
from typing import Any


# ========= TokenFormatter =========
class TokenFormatter:
    # ひらがな→カタカナ
    def _hira_to_kata(self, s: str) -> str:
        def conv(m):
            code = ord(m.group(0)) + 0x60
            return chr(code)

        return re.sub(r"[\u3041-\u3096]", conv, s)

    def _remove_sign_pronunciation(
        self, tokens: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        # 記号: 発音を表層形に
        # (JS コメントは「空文字にする」だが、実装は surface を入れている）
        for t in tokens:
            if t.get("pos") == "記号":
                t["pronunciation"] = t.get("surface_form", "")
        return tokens

    def _remove_unknown_sahen(
        self, tokens: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        # サ変接続で発音が未定義なら pos を記号に
        for t in tokens:
            if (
                t.get("pos") == "名詞"
                and t.get("pos_detail_1") == "サ変接続"
                and not t.get("pronunciation")
            ):
                t["pos"] = "記号"
                t["pronunciation"] = ""
        return tokens

    def _is_small_kana_start(self, ch: str) -> bool:
        return (
            re.match(r"^[ぁぃぅぇぉゃゅょゎっァィゥェォヮャュョッ]", ch or "")
            is not None
        )

    def _is_kana_end(self, ch: str) -> bool:
        return re.search(r"[ぁ-ゔァ-ヴ]$", ch or "") is not None

    def _is_kana(self, text: str) -> bool:
        return re.match(r"^[ぁ-ゔァ-ヴー]+$", text or "") is not None

    def _concat_small_kana(self, tokens: list[dict[str, Any]]) -> list[dict[str, str]]:
        # 小書きかなを直前トークンに結合
        for i in range(1, len(tokens)):
            if self._is_small_kana_start(
                tokens[i].get("surface_form", "")
            ) and self._is_kana_end(tokens[i - 1].get("surface_form", "")):
                tokens[i - 1]["surface_form"] = tokens[i - 1].get(
                    "surface_form", ""
                ) + tokens[i].get("surface_form", "")
                tokens[i - 1]["pronunciation"] = tokens[i - 1].get(
                    "pronunciation", ""
                ) + tokens[i].get("pronunciation", "")
                tokens[i]["is_remove"] = True
        tokens = [v for v in tokens if not v.get("is_remove")]
        return tokens

    def _set_unknown_word_pronunciation(
        self, tokens: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        # 不明語（Kanaのみ）の読みを表層から設定
        for t in tokens:
            if t.get("word_type") == "UNKNOWN" and self._is_kana(
                t.get("surface_form", "")
            ):
                t["pronunciation"] = self._hira_to_kata(t.get("surface_form", ""))
        return tokens

    def _set_kana_pronunciation(
        self, tokens: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        # Kana の場合は読みを表層から、pos が記号なら名詞へ
        for t in tokens:
            s = t.get("surface_form", "")
            if self._is_kana(s):
                t["pronunciation"] = self._hira_to_kata(s)
                if t.get("pos") == "記号":
                    t["pos"] = "名詞"
        return tokens

    def _concat_single_bar(self, tokens: list[dict[str, str]]) -> list[dict[str, str]]:
        # 長音記号単独トークンを直前に結合
        for i in range(1, len(tokens)):
            if tokens[i].get("surface_form") == "ー":
                tokens[i - 1]["surface_form"] = (
                    tokens[i - 1].get("surface_form", "") + "ー"
                )
                tokens[i - 1]["pronunciation"] = (
                    tokens[i - 1].get("pronunciation", "") + "ー"
                )
        tokens = [t for t in tokens if t.get("surface_form") != "ー"]
        return tokens

    def _set_number_pronunciation(
        self, tokens: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
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
        for t in tokens:
            s = t.get("surface_form", "")
            if re.match(r"^[0-9]$", s):
                p = "".join(n2p[v] for v in s)
                t["pronunciation"] = p
        return tokens

    def _set_phrase_index(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cnt = 0
        for idx, t in enumerate(tokens):
            if idx == 0:
                t["phrase"] = 0
                continue
            if t.get("pos") in ["名詞", "動詞", "副詞", "形容詞", "形容動詞", "感動詞"]:
                cnt += 1
            t["phrase"] = cnt
        return tokens

    def format(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tokens = self._remove_sign_pronunciation(tokens)
        tokens = self._remove_unknown_sahen(tokens)
        tokens = self._set_number_pronunciation(tokens)
        # tokens = self._set_unknown_word_pronunciation(tokens)
        # 元コードではコメントアウト
        tokens = self._set_kana_pronunciation(tokens)
        tokens = self._concat_single_bar(tokens)
        tokens = self._concat_small_kana(tokens)
        tokens = self._set_phrase_index(tokens)
        return tokens


# ========= Kanji =========
class Kanji:
    """
    dictionary: dict[str, list[str]]
      各漢字に対応する読み候補（カタカナ）の配列（長い順でソート済みを想定）
    """

    def __init__(self, dictionary: dict[str, list[str]]):
        self.dictionary = dictionary

    def _kanji_allocate(
        self, surface: str, pronunciation: str, kanji_dict: dict[str, list[str]]
    ) -> list[tuple[str, str]]:
        rest_text = pronunciation
        skipped_char = ""
        output: list[tuple[str, str]] = []

        for ch in surface:
            if ch not in kanji_dict:
                skipped_char += ch
                continue

            yomi_candidates = kanji_dict[ch]  # 長さ降順を想定
            start = -1
            yomi = ""
            for y in yomi_candidates:
                start = rest_text.find(y)
                if start >= 0:
                    yomi = y
                    break

            # マッチしないならスキップ
            if start == -1:
                skipped_char += ch
                continue

            if start > 0:
                if not output:
                    if skipped_char != "":
                        output.append((skipped_char, rest_text[:start]))
                        skipped_char = ""
                        rest_text = rest_text[start:]
                        output.append((ch, yomi))
                        rest_text = rest_text[len(yomi) :]
                    else:
                        output.append((ch, rest_text[: start + len(yomi)]))
                        rest_text = rest_text[start + len(yomi) :]
                elif skipped_char != "":
                    output.append((skipped_char, rest_text[:start]))
                    skipped_char = ""
                    rest_text = rest_text[start:]
                    output.append((ch, yomi))
                    rest_text = rest_text[len(yomi) :]
                else:
                    # 直前の要素の yomi に追加
                    prev_s, prev_y = output[-1]
                    output[-1] = (prev_s, prev_y + rest_text[:start])
                    rest_text = rest_text[start:]
                    output.append((ch, yomi))
                    rest_text = rest_text[len(yomi) :]
            else:
                output.append((ch, yomi))
                rest_text = rest_text[len(yomi) :]

        # 末尾処理
        if skipped_char != "":
            if rest_text != "" or not output:
                output.append((skipped_char, rest_text))
            else:
                prev_s, prev_y = output[-1]
                output[-1] = (prev_s + skipped_char, prev_y)
        elif rest_text != "" and output:
            prev_s, prev_y = output[-1]
            output[-1] = (prev_s, prev_y + rest_text)

        return output

    def _is_fullmatch(self, text: str) -> bool:
        return re.match(r"^[一-龠]+$", text or "") is not None

    def to_kana(self, text: str) -> str:
        kana = []
        for ch in text:
            if ch in self.dictionary:
                kana.append(self.dictionary[ch][0])
        return "".join(kana)

    # 公開 API
    def allocate(self, surface: str, pronunciation: str) -> list[tuple[str, str]]:
        return self._kanji_allocate(surface, pronunciation, self.dictionary)


# ========= Character =========
class Character:
    def __init__(self, kanji: Kanji):
        # print("kanji in Character", kanji)
        self.kanji = kanji

    def _kana_tokenize(self, text: str) -> list[dict[str, str]]:
        if text == "":
            return []
        # カタカナ / ひらがな / 非カナ の 3 グループ
        pattern = re.compile(
            r"(?P<kata>[ァ-ヴー]+)|(?P<hira>[ぁ-ゔー]+)|(?P<nonkana>[^ぁ-ゔァ-ヴー]+)"
        )
        out = []
        for m in pattern.finditer(text):
            g = m.groupdict()
            token = {}
            for k, v in g.items():
                if v:
                    token = {"surface_form": v, "type": k}
                    break
            out.append(token)
        return out

    def _hira_to_kata(self, s: str) -> str:
        def conv(m):
            code = ord(m.group(0)) + 0x60
            return chr(code)

        return re.sub(r"[\u3041-\u3096]", conv, s)

    def _balanced_allocate(
        self, surface: str, pronunciation: str
    ) -> list[dict[str, Any]]:
        # surface と pronunciation の長さバランスで対応を割り振る
        text = {"surface_form": surface, "pronunciation": pronunciation}
        longer = "surface_form"
        shorter = "pronunciation"
        if len(surface) <= len(pronunciation):
            longer = "pronunciation"
            shorter = "surface_form"

        plusone = (
            len(text[longer]) % len(text[shorter]) if len(text[shorter]) > 0 else 0
        )
        contentlen = (
            len(text[longer]) // len(text[shorter]) if len(text[shorter]) > 0 else 0
        )

        output = []
        longer_pos = 0
        for i in range(len(text[shorter])):
            longer_content_len = contentlen
            if i < plusone:
                longer_content_len += 1

            if longer == "pronunciation":
                for j in range(longer_content_len):
                    info = {
                        longer: text[longer][longer_pos + j],
                        shorter: text[shorter][i],
                        "in_surface_pos": j,
                    }
                    output.append(info)
                longer_pos += longer_content_len
            else:
                info = {
                    longer: text[longer][longer_pos : longer_pos + longer_content_len],
                    shorter: text[shorter][i],
                    "in_surface_pos": 0,
                }
                longer_pos += longer_content_len
                output.append(info)
        return output

    def _kana_allocate(
        self, separated_surface: list[dict[str, str]], pronunciation: str
    ) -> list[dict[str, Any]]:
        if len(separated_surface) == 0:
            return []

        output = []
        rest_text = pronunciation

        for i in range(len(separated_surface)):
            typ = separated_surface[i]["type"]
            surface = separated_surface[i]["surface_form"]

            if typ == "nonkana":
                continue

            katakana = surface if typ == "kata" else self._hira_to_kata(surface)
            start = rest_text.find(katakana)

            if start > 0:
                nonkana = separated_surface[i - 1]
                # JS の slice(0, start - len(rest_text)) は Python では
                # rest_text[:start] と等価
                output.append(
                    {
                        "surface_form": nonkana["surface_form"],
                        "pronunciation": rest_text[:start],
                        "type": nonkana["type"],
                    }
                )
                rest_text = rest_text[start:]

            output.append(
                {
                    "surface_form": surface,
                    "pronunciation": rest_text[: len(katakana)],
                    "type": typ,
                }
            )
            rest_text = rest_text[len(katakana) :]

        if rest_text != "":
            last = separated_surface[-1]
            output.append(
                {
                    "surface_form": last["surface_form"],
                    "pronunciation": rest_text,
                    "type": last["type"],
                }
            )
        return output

    def _concat_sign_token(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted = []
        for t in tokens:
            if t.get("type") == "sign":
                if formatted:
                    formatted[-1]["surface_form"] = formatted[-1].get(
                        "surface_form", ""
                    ) + t.get("surface_form", "")
                continue
            else:
                formatted.append(t)
        return formatted

    def _get_char_correspondence(
        self, tokens: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # token index 付与
        for idx, t in enumerate(tokens):
            t["token_index"] = idx

        # カナ部分と非カナ部分対応
        kana_correspondence: list[dict[str, Any]] = []
        for token in tokens:
            if not token.get("pronunciation"):
                token["pronunciation"] = ""
            separated = self._kana_tokenize(token.get("surface_form", ""))
            correspond = self._kana_allocate(separated, token.get("pronunciation", ""))

            # 記号なら type=sign に
            if token.get("pos") == "記号":
                for v in correspond:
                    v["type"] = "sign"

            # 元の token 情報をコピー
            for v in correspond:
                for k, val in token.items():
                    if k not in v:
                        v[k] = val
            kana_correspondence.extend(correspond)

        # 1 文字ずつ対応
        char_correspondence: list[dict[str, Any]] = []
        subword_index = -1

        for token in kana_correspondence:
            ttype = token.get("type")
            surf = token.get("surface_form", "")
            pron = token.get("pronunciation", "")

            if (
                ttype == "nonkana"
                and len(surf) > 1
                and re.match(r"^[\w']+$", surf) is None
            ):
                # 漢字（熟語）など
                pairs = self.kanji.allocate(surf, pron)  # List[Tuple[surface, yomi]]
                block: list[dict[str, Any]] = []
                for surface_form, yomi in pairs:
                    c = self._balanced_allocate(surface_form, yomi)
                    if len(surface_form) > 1:
                        # 小文字始まりの読みを調整（元コードのロジックを踏襲）
                        for i in range(len(c)):
                            v = c[i]
                            if (
                                re.match(
                                    r"^[ァィゥェォヮャュョ]", v.get("pronunciation", "")
                                )
                                and v.get("in_surface_pos") == 0
                                and i > 0
                            ):
                                for j in range(i - 1, len(c)):
                                    if (
                                        j >= i - 1 + 2
                                        and c[j].get("in_surface_pos") == 0
                                    ):
                                        break
                                    c[j]["in_surface_pos"] = j - i + 1
                                    c[j]["surface_form"] = v["surface_form"]
                    subword_index += 1
                    for e in c:
                        e["subword"] = subword_index
                    block.extend(c)

                # 元 token 情報をコピー
                for v in block:
                    for k, val in token.items():
                        if k not in v:
                            v[k] = val
                char_correspondence.extend(block)
            else:
                c = self._balanced_allocate(surf, pron)
                subword_index += 1
                for e in c:
                    e["subword"] = subword_index
                    for k, val in token.items():
                        if k not in e:
                            e[k] = val
                char_correspondence.extend(c)

        # surface の index を付与
        index = -1
        for v in char_correspondence:
            if v.get("in_surface_pos") == 0:
                index += 1
            v["char_index"] = index

        char_correspondence = self._concat_sign_token(char_correspondence)
        return char_correspondence

    # 公開 API
    def tokenize(self, tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._get_char_correspondence(tokens)


if __name__ == "__main__":
    # Example usage
    kanji_dict = {
        "漢": ["カン"],
        "字": ["ジ"],
        "語": ["ゴ"],
        "熟": ["ジュク"],
    }
    kanji = Kanji(kanji_dict)
    character = Character(kanji)

    tokens = [
        {"surface_form": "漢字", "pronunciation": "カンジー", "pos": "名詞"},
        {"surface_form": "じゃ", "pronunciation": "ジャ", "pos": "助詞"},
        {"surface_form": "語", "pronunciation": "カタリ", "pos": "名詞"},
    ]

    result = character.tokenize(tokens)
    for r in result:
        print(r)
