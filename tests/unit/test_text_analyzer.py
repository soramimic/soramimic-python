from soramimic_python.core.loader import _text_analyzer

class TestTextAnalyzerTokenizeTogether:
    def test_正常系_英語カナ変換(self):
        """テキストをトークン化するテスト。"""
        
        # テストケース
        test_cases = [
            ["Hello World", "ヘロー ワールド"],
            ["SoraMimi Python", "ソラミー ピソン"],
            ["Test Text Analyzer", "テスト テキスト アナライザー"],
            ["Tokenize Together", "トークナイズ トジェザー"],
            ["I'm fineは元気です", "エム ファイン ワ ゲンキ デス"],
        ]

        for text, expected in test_cases:
            result = _text_analyzer.tokenize_together([text])[0]
            pronunciations = " ".join(token["pronunciation"] for token in result)
            assert pronunciations == expected
    
    def test_正常系_助詞の発音(self):
        """助詞の発音が正しく変換されるかのテスト。"""
        
        # テストケース
        test_cases = [
            ("私は元気です", "ワタシ ワ ゲンキ デス"),
            ("どこへ？", "ドコ エ ？"),
            ("桃を食べる", "モモ オ タベル"),
        ]

        for text, expected in test_cases:
            result = _text_analyzer.tokenize_together([text])[0]
            pronunciations = " ".join(token["pronunciation"] for token in result)
            assert pronunciations == expected

class TestTextAnalyzerGetYomiFromToken:
    def test_正常系_助詞の発音(self):
        """助詞の発音が正しく取得できるかのテスト。"""

        # テストケース
        test_cases = [
            ("私は", "ワタシワ"),
            ("どこへ", "ドコエ"),
            ("桃を", "モモオ"),
        ]

        for text, expected in test_cases:
            tokens = _text_analyzer.tokenize_together([text])[0]
            result = _text_analyzer.get_yomi_from_tokens(tokens)
            assert result == expected
