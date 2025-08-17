from soramimic_python.core.mecab_tokenizer import MeCabTokenizer


class TestMeCabTokenizer_ParseText:
    def test_正常系_助詞の発音(self):
        """助詞の発音が正しく変換されるかのテスト。"""

        # テストケース
        test_cases = [
            ("私は元気です", "ワタシワゲンキデス"),
            ("どこへ？", "ドコエ？"),
            ("桃を食べる", "モモオタベル"),
        ]

        tokenizer = MeCabTokenizer()
        for text, expected in test_cases:
            result = tokenizer.tokenize(text)
            pronunciations = "".join(token["pronunciation"] for token in result)
            assert pronunciations == expected

    def test_正常系_長いひらがな(self):
        """助詞の発音が正しく変換されるかのテスト。"""

        # テストケース
        test_cases = [
            ("うさぎおいしかのやま", "ウサ*")
        ]

        tokenizer = MeCabTokenizer()
        for text, expected in test_cases:
            result = tokenizer.tokenize(text)
            pronunciations = "".join(token["pronunciation"] for token in result)
            assert pronunciations == expected
