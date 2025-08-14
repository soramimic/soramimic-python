import tempfile

from soramimic_python.core.soramimic import Mora, ParodyWord, load_wordlist


def create_sample_wordlist() -> str:
    """
    Creates a sample wordlist for testing purposes.

    Returns:
        str: Path to the created temporary CSV file
    """
    csv_string = (
        "id,surface,pronunciation\n"
        "日本,日本,ニッポン\n"
        "日本,日本,ニホン\n"
        "韓国,韓国,カンコク\n"
    )

    # Create a temporary file with CSV content
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as temp_file:
        temp_file.write(csv_string)
        temp_path = temp_file.name

    return temp_path


class TestLoadWordList:
    def test_正常系_単語リストが正しく読み込まれる(self) -> None:
        """単語リストが正しく読み込まれることを確認するテスト。"""

        csv_path = create_sample_wordlist()
        wordlist = load_wordlist(csv_path)
        assert wordlist[0] == ParodyWord(
            id="日本",
            moras=[
                Mora(surface="日本", mora="ニッ", is_phrase_start=True),
                Mora(surface="", mora="ポン", is_phrase_start=False),
            ],
        )
