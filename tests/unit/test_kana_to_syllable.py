from soramimic_python.core.kana_to_syllable import vowel_to_bar


class TestVowelToBar:
    def test_正常系(self):
        test_cases = [
            ("アア", "アー"),
            ("オウ", "オー"),
            ("オウウ", "オーウ"),
            ("ヘイセイ", "ヘーセー"),
            ("ヘイイン", "ヘーイン"),
            ("ジェイン", "ジェーン"),
            ("ジャアン", "ジャーン"),
            ("シイテキ", "シーテキ"),
            ("スウジ", "スージ"),
            ("キュウキョ", "キューキョ"),
            ("ジョウ", "ジョー"),
            ("ジョウトウ", "ジョートー"),
        ]

        for kana, expected in test_cases:
            result = vowel_to_bar(kana)
            assert result == expected, f"Expected {expected}, but got {result}"
