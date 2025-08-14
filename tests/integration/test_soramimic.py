from soramimic_python.core.loader import soramimi_maker, wordlist
from pathlib import Path
words_tidy_dir = Path(__file__).resolve().parent.parent.parent / "src/soramimic_python/words_tidy"
nations_path = words_tidy_dir / "nations.csv"

with open(nations_path) as f:
    csv_text = f.read()
nation_words = wordlist.parseTidy(csv_text)

#print(nation_words)
class TestSoramimic:
    def test_正常系(self):
        results = soramimi_maker.generate(["うさぎおいしかのやま"], nation_words, {}, lambda x1, x2, x3: print(x1, x2, x3), lambda x: print(x))
        result_words = [word["surface"] for word in results[0]]
        assert result_words == ["イタリア", "フィジー", "ガーナ", "ミャンマー"]

