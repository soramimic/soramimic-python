from soramimic_python.core.mecab_tokenizer import MeCabTokenizer

class TestMeCabTokenizer_ParseText:
    def test_正常系_助詞の発音(self):
        """助詞の発音が正しく変換されるかのテスト。"""
        
        # テストケース
        test_cases = [
            ("私は元気です", "ワタシ ワ ゲンキ デス"),
            ("どこへ？", "ドコ エ ？"),
            ("桃を食べる", "モモ オ タベル"),
        ]

        tokenizer = MeCabTokenizer()
        for text, expected in test_cases:
            result = tokenizer.tokenize(text)
            pronunciations = " ".join(token["pronunciation"] for token in result)
            assert pronunciations == expected