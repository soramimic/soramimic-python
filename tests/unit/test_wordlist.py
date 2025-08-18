"""convert_where_query_to_pandas関数のテスト"""

import pytest

from soramimic_python.core.wordlist import convert_where_query_to_pandas


class TestConvertWhereQueryToPandas:
    """convert_where_query_to_pandas関数のテストクラス"""

    def test_正常系_単一の等価条件(self):
        """等価条件（=）を1つ含むクエリが正しくpandas形式に変換される"""
        # Arrange
        where = "type=family"
        expected = "type=='family'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_正常系_単一の不等価条件(self):
        """不等価条件（!=）を1つ含むクエリが正しくpandas形式に変換される"""
        # Arrange
        where = "status!=active"
        expected = "status!='active'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_正常系_複数の等価条件をorで結合(self):
        """or演算子で結合された複数の等価条件が正しく変換される"""
        # Arrange
        where = "type=family or type=registered"
        expected = "type=='family' or type=='registered'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_正常系_複数の条件をandで結合(self):
        """and演算子で結合された複数の条件が正しく変換される"""
        # Arrange
        where = "type=family and status=active"
        expected = "type=='family' and status=='active'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_正常系_等価と不等価の混合条件(self):
        """等価条件と不等価条件が混合されたクエリが正しく変換される"""
        # Arrange
        where = "type=family and status!=inactive"
        expected = "type=='family' and status!='inactive'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_正常系_スペースを含む条件(self):
        """演算子の前後にスペースが含まれる条件が正しく変換される"""
        # Arrange
        where = "type = family and status != active"
        expected = "type=='family' and status!='active'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_正常系_複雑な複合条件(self):
        """複数の条件とor/and演算子を組み合わせた複雑なクエリが正しく変換される"""
        # Arrange
        where = "type=family or type=registered and status!=pending"
        expected = "type=='family' or type=='registered' and status!='pending'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_エッジケース_空文字列(self):
        """空文字列が入力された場合は空文字列が返される"""
        # Arrange
        where = ""
        expected = ""

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_エッジケース_条件演算子を含まない文字列(self):
        """= や != を含まない文字列はそのまま返される"""
        # Arrange
        where = "some text without operators"
        expected = "some text without operators"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_エッジケース_数値を含む条件(self):
        """数値を含む条件が正しく変換される"""
        # Arrange
        where = "count=10 and level!=5"
        expected = "count=='10' and level!='5'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_エッジケース_アンダースコアを含むフィールド名(self):
        """アンダースコアを含むフィールド名が正しく処理される"""
        # Arrange
        where = "field_name=value and other_field!=test"
        expected = "field_name=='value' and other_field!='test'"

        # Act
        result = convert_where_query_to_pandas(where)

        # Assert
        assert result == expected

    def test_異常系_None入力(self):
        """None が入力された場合は TypeError が発生する"""
        # Arrange
        where = None

        # Act & Assert
        with pytest.raises(TypeError):
            convert_where_query_to_pandas(where)
