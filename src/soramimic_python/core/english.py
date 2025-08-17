import re
from typing import Any

import neologdn
from e2k import C2K, NGram

c2k = C2K()
ngram = NGram()


class Apostrophe:
    """
    JS Apostrophe() を Python へ移植
    - to_string: ’ と ' をプレースホルダ "APOSTROPHE" に置換
    - to_sign:   プレースホルダを ' に戻す
    - remove_string: プレースホルダを削除
    - include:  プレースホルダを含むか
    - format:   全角風の ’ を ' に正規化
    """

    STRING_APOSTROPHE = "APOSTROPHE"

    def to_string(self, text: str) -> str:
        # JS: text.split("’").join("'").split("'").join(STRING_APOSTROPHY)
        return text.replace("’", "'").replace("'", self.STRING_APOSTROPHE)

    def to_sign(self, text: str) -> str:
        return text.replace(self.STRING_APOSTROPHE, "'")

    def remove_string(self, text: str) -> str:
        return text.replace(self.STRING_APOSTROPHE, "")

    def include(self, text: str) -> bool:
        return self.STRING_APOSTROPHE in text

    def format(self, text: str) -> str:
        # /[’]/g -> "'"
        return re.sub(r"[’]", "'", text)


class English:
    """
    JS English(DICTIONARY, TREE) を Python へ移植
    - DICTIONARY: 英単語→カナ、かつ単文字 A..Z → カナ を含む dict を想定
    - TREE: ローマ字→カナのトライ（ネスト dict; 葉は str カナ）
    - tokenizer: .tokenize(str) -> List[dict(surface_form, pronunciation, ...)]
    """

    def __init__(self, DICTIONARY: dict[str, str], TREE: dict[str, Any]):
        self.DICTIONARY = DICTIONARY
        self.TREE = TREE
        self.apostrophe = Apostrophe()

    def _zenkaku_english_to_hankaku(self, text: str) -> str:
        # /[Ａ-Ｚａ-ｚ]/ を半角へ（英字のみ）
        def conv(m):
            ch = m.group(0)
            return chr(ord(ch) - 65248)

        return re.sub(r"[Ａ-Ｚａ-ｚ]", conv, text)

    def _roman_to_kana(self, text: str, tree: dict[str, Any]) -> str:
        """
        JS romanToKana をそのまま移植。
        - 英字のみを対象（a-z）。それ以外の文字が来たらそのまま出力。
        - 子音重複→促音、末尾 n → ン を処理
        - trie(TREE) で最長一致（葉が文字列なら確定出力）
        """
        s_lower = text.lower()
        result = ""
        tmp = ""  # 途中まで積んだ元のケースの文字列
        index = 0
        node = tree

        def push(chars: str, to_root: bool = True):
            nonlocal result, tmp, node
            result += chars
            tmp = ""
            node = tree if to_root else node

        while index < len(s_lower):
            ch_low = s_lower[index]
            ch_orig = text[index]

            if re.match(r"[a-z]", ch_low):
                if ch_low in node:
                    nxt = node[ch_low]
                    if isinstance(nxt, str):
                        # ここで確定：カナ追加、ルートに戻す
                        push(nxt)
                    else:
                        # まだ枝の途中：原文の文字を tmp に積む、node を進める
                        tmp += ch_orig
                        node = nxt
                    index += 1
                    continue

                # ここに来たら現在の node では一致しない
                prev = s_lower[index - 1] if index > 0 else ""
                if prev and prev in ("n", ch_low):
                    # 促音 or 'n'
                    push("ン" if prev == "n" else "ッ", to_root=False)

                # いったん仕切り直し（ルートに戻して再解釈）
                if node is not tree and ch_low in tree:
                    push(tmp)  # 途中まで積んだ未確定分をそのまま出力
                    continue

            # 英字でない or どうにもならないので、tmp + 現文字をそのまま出力
            push(tmp + ch_orig)
            index += 1

        # 末尾の n は ン に変換
        if tmp.endswith("n"):
            tmp = re.sub(r"n$", "ン", tmp)
        push(tmp)
        return result

    def _english_word_to_kana(self, text: str, dictionary: dict[str, str]) -> str:
        upper = text.upper()
        return dictionary.get(upper, text)

    def _alphabet_to_kana(self, text: str, dictionary: dict[str, str]) -> str:
        # 英字単体を辞書の対応へ（例: A->エー など）
        t = text.upper()
        found = re.findall(r"[A-Z]", t)
        if found:
            for v in found:
                if v in dictionary:
                    t = t.replace(v, dictionary[v])
        return t

    def _english_to_kana(
        self, text: str, dictionary: dict[str, str], tree: dict[str, Any]
    ) -> str:
        # t = self._zenkaku_english_to_hankaku(text)
        t = neologdn.normalize(text)
        # t = self._english_word_to_kana(t, dictionary)
        # t = self._roman_to_kana(t, tree)
        # t = self._alphabet_to_kana(t, dictionary)
        if ngram(t):
            return c2k(t)
        else:
            return ngram.as_is(t)

    def is_fullmatch(self, text: str) -> bool:
        return re.fullmatch(r"[a-zA-Z']+", text) is not None

    def _tokenize(self, text: str, tokenizer) -> list[dict[str, Any]]:
        # 1) アポストロフィを一時トークンに置換してからトークナイズ
        str_val = self.apostrophe.to_string(text)
        tokens = tokenizer.tokenize(str_val)

        # 2) 英単語のみの token は surface を元に戻し、発音が "*" の場合は英語→カナへ
        out = []
        for token in tokens:
            surf = token.get("surface_form", "")
            pron = token.get("pronunciation", "")

            if self.is_fullmatch(surf):
                # APOSTROPHE を ' に戻す
                surf_fixed = self.apostrophe.to_sign(surf)
                token["surface_form"] = surf_fixed

                if pron == "*":
                    token["pronunciation"] = self._english_to_kana(
                        surf_fixed, self.DICTIONARY, self.TREE
                    )
            out.append(token)
        return out

    def to_kana(self, text: str) -> str:
        return self._english_to_kana(text, self.DICTIONARY, self.TREE)


if __name__ == "__main__":
    # Example usage
    english_dict = {"HELLO": "ハロー", "WORLD": "ワールド"}
    roman_tree = {
        "h": {"e": {"l": {"l": {"o": "ハロー"}}}},
        "w": {"o": {"r": {"l": {"d": "ワールド"}}}},
    }
    english = English(english_dict, roman_tree)

    text = "Hello World"
    tokens = english._tokenize(text)
    for token in tokens:
        print(token)
