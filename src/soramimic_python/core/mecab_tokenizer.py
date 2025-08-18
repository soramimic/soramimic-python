import MeCab


class MeCabTokenizer:
    """
    MeCabライブラリを直接使用したトークナイザー。
    JS版のAPIコールの代わりに、ローカルのMeCabインスタンスを使用する。
    """

    def __init__(self, dictionary_path: str | None = None):
        """
        MeCabインスタンスを初期化

        Args:
            dictionary_path: MeCab辞書のパス（Noneの場合はシステムデフォルト）
        """
        # MeCabのオプション設定
        # 出力フォーマット: 表層形\t品詞,品詞細分類1,品詞細分類2,品詞細分類3,
        # 活用型,活用形,原形,読み,発音
        mecab_args = ""  # ipadic形式（デフォルト）
        if dictionary_path:
            mecab_args += f" -d {dictionary_path}"

        try:
            self.mecab = MeCab.Tagger(mecab_args)
        except Exception as e:
            # フォールバック: デフォルト設定
            print(f"MeCab初期化警告: {e}")
            self.mecab = MeCab.Tagger()

    def tokenize(self, text: str) -> list[dict[str, str]]:
        """
        text が文字列: 1文のKuromoji風トークン配列を返す
        text が配列  : 各要素ごとにトークン配列を返す（配列の配列）
        """
        return self._parse_text(text)

    def get_yomi(self, text: str) -> str:
        """
        読み（カタカナ）を返す
        """
        return self._extract_reading(text)

    def _parse_text(self, text: str) -> list[dict[str, str]]:
        """MeCabでテキストを解析し、Kuromoji風のトークン配列に変換"""
        if not text.strip():
            return []

        # MeCabで解析
        parsed = self.mecab.parse(text)
        lines = parsed.strip().splitlines()[:-1]  # 最後のEOS行を除外

        tokens = []
        for line in lines:
            # ipadic形式の解析:
            # 表層形\t品詞,品詞細分類1,品詞細分類2,品詞細分類3,
            # 活用型,活用形,原形,読み,発音
            parts = line.split("\t")
            if len(parts) < 2:
                continue

            surface = parts[0]
            features = parts[1].split(",") if len(parts) > 1 else []

            # 各フィールドを取得（不足分は空文字）
            part_of_speech = features[0] if len(features) > 0 else "未知"
            part_of_speech_level_1 = features[1] if len(features) > 1 else "*"
            part_of_speech_level_2 = features[2] if len(features) > 2 else "*"
            part_of_speech_level_3 = features[3] if len(features) > 3 else "*"
            conjugation_type = features[4] if len(features) > 4 else "*"
            conjugation_form = features[5] if len(features) > 5 else "*"
            basic_form = features[6] if len(features) > 6 else "*"
            reading = features[7] if len(features) > 7 else "*"
            pronunciation = features[8] if len(features) > 8 else "*"

            if pronunciation == "ヲ":
                pronunciation = "オ"

            # Kuromoji風の形式に変換
            token = {
                "surface_form": surface,
                "part_of_speech": part_of_speech,
                "part_of_speech_level_1": part_of_speech_level_1,
                "part_of_speech_level_2": part_of_speech_level_2,
                "part_of_speech_level_3": part_of_speech_level_3,
                "conjugation_type": conjugation_type,
                "conjugation_form": conjugation_form,
                "basic_form": basic_form,
                "reading": reading,
                "pronunciation": pronunciation,
            }

            tokens.append(token)

        return tokens

    def _extract_reading(self, text: str) -> str:
        """テキストから読み（カタカナ）を抽出"""
        tokens = self._parse_text(text)
        readings = []

        for token in tokens:
            reading = token.get(
                "pronunciation", token.get("reading", token["surface_form"])
            )
            # ひらがなをカタカナに変換
            reading = self._hira_to_kata(reading)
            readings.append(reading)

        return "".join(readings)

    @staticmethod
    def _hira_to_kata(text: str) -> str:
        """ひらがなをカタカナに変換"""
        result = ""
        for char in text:
            if "\u3041" <= char <= "\u3096":  # ひらがな
                result += chr(ord(char) + 0x60)  # カタカナに変換
            else:
                result += char
        return result


if __name__ == "__main__":
    tokenizer = MeCabTokenizer()
    text = "どこへ？"
    print(tokenizer.tokenize(text))
