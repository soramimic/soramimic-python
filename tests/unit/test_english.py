from soramimic_python.core.loader import _english as english
class TestEnglishToKana:
    def test_正常系_英語をカタカナに変換(self) -> None:
        """英語の単語をカタカナに変換するテスト。"""
        
        # テストケース
        test_cases = [
            ("hello", "ヘロー"),
            ("world", "ワールド"),
            ("soramimic", "ソラミー"),
            ("python", "ピソン"),
            ("test", "テスト"),
        ]
        
        for word, expected in test_cases:
            result = english.to_kana(word)
            assert result == expected, f"Expected '{expected}' but got '{result}' for word '{word}'"