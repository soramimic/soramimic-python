from soramimic_python.core.loader import _character, _text_analyzer


class TestCharacterTokenize:
    def test_正常系_二字熟語(self):
        """テキストが正しくトークン化されるかのテスト。"""

        # テストケース
        test_cases = [
            (
                "漢字",
                [
                    {"surface_form": "漢", "pronunciation": "カ"},
                    {"surface_form": "漢", "pronunciation": "ン"},
                    {"surface_form": "字", "pronunciation": "ジ"},
                ],
            )
        ]

        for text, expected in test_cases:
            tokens = _text_analyzer.tokenize_together([text])[0]

            result = _character.tokenize(tokens)

            # resultが少なくともexpectedのkeyを含むことをチェック
            assert len(result) == len(expected)
            for actual_item, expected_item in zip(result, expected, strict=False):
                for key, expected_value in expected_item.items():
                    assert actual_item[key] == expected_value, (
                        f"Value mismatch for key '{key}': expected {expected_value}, got {actual_item[key]}"
                    )

    def test_正常系_ひらがな(self):
        """テキストが正しくトークン化されるかのテスト。"""

        # テストケース
        test_cases = [
            (
                "うさぎおいしかのやま",
                [
                    {"surface_form": "う", "pronunciation": "ウ"},
                    {"surface_form": "さ", "pronunciation": "サ"},
                    {"surface_form": "ぎ", "pronunciation": "ギ"},
                    {"surface_form": "お", "pronunciation": "オ"},
                    {"surface_form": "い", "pronunciation": "イ"},
                    {"surface_form": "し", "pronunciation": "シ"},
                    {"surface_form": "か", "pronunciation": "カ"},
                    {"surface_form": "の", "pronunciation": "ノ"},
                    {"surface_form": "や", "pronunciation": "ヤ"},
                    {"surface_form": "ま", "pronunciation": "マ"},
                ],
            )
        ]

        for text, expected in test_cases:
            tokens = _text_analyzer.tokenize_together([text])[0]

            result = _character.tokenize(tokens)

            # resultが少なくともexpectedのkeyを含むことをチェック
            assert len(result) == len(expected)
            for actual_item, expected_item in zip(result, expected, strict=False):
                for key, expected_value in expected_item.items():
                    assert actual_item[key] == expected_value, (
                        f"Value mismatch for key '{key}': expected {expected_value}, got {actual_item[key]}"
                    )
