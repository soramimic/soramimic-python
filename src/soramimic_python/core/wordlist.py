import re
from collections.abc import Callable
from io import StringIO
from typing import Any, TypedDict
from soramimic_python.core.text_analyzer import tokenize

import pandas as pd


class ParodyWord(TypedDict, total=False):
    id: str
    surface: str
    pronunciation: str
    kana: str
    original: str


def convert_where_query_to_pandas(where: str) -> str:
    """
    既存のクエリ形式をpandas.DataFrame.query()形式に変換する。

    Args:
        where: 既存形式のクエリ文字列 (例: "type=family or type=registered")

    Returns:
        pandas形式のクエリ文字列 (例: "type=='family' or type=='registered'")
    """
    # != を !='' に変換（値をクォートで囲む）
    where_pandas = re.sub(r"(\w+)\s*!=\s*(\w+)", r"\1!='\2'", where)
    # = を =='' に変換（値をクォートで囲む）
    where_pandas = re.sub(r"(\w+)\s*=\s*(\w+)", r"\1=='\2'", where_pandas)
    return where_pandas


class WordList:
    """
    JS WordList(textAnalyzer) を Python へ移植。
    - parse_tidy: tidy CSV テキストと where 句（任意）を受けて {長さ: [語…]} を返す
    - parse_plain: プレーンテキストを CSV に変換してから同上
    語オブジェクトの形:
      {
        "surface": <表層>,
        "pronunciation": <バリエーション（各候補のカナ連結）>,
        "kana": <元の正規化読みに相当>,
        "id": <id>,
        "original": <元タイトル>
      }
    """

    def __init__(self, text_analyzer):
        self.text_analyzer = text_analyzer

    # ---- core helpers ----
    @staticmethod
    def _has_kanji(s: str) -> bool:
        return re.search(r"[一-龠]", s) is not None

    # ---- tidy CSV text loader ----
    def _prepare_pronunciation_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        pronunciation列の前処理を行う。
        
        Args:
            df: 入力DataFrame
            
        Returns:
            pronunciation列が処理されたDataFrame
        """
        # pronunciationが無い/NAのときはsurfaceを採用
        if "pronunciation" not in df.columns:
            df["pronunciation"] = df["surface"]
        else:
            df["pronunciation"] = df["pronunciation"].fillna(df["surface"])
            df.loc[df["pronunciation"].str.lower() == "na", "pronunciation"] = df[
                "surface"
            ]

        # かな推定（漢字を含む行だけ個別にget_yomiを呼び出し）
        kanji_mask = df["pronunciation"].apply(self._has_kanji)
        kanji_rows = df.loc[kanji_mask, "pronunciation"]

        for idx in kanji_rows.index:
            yomi_result = self.text_analyzer.get_yomi(df.at[idx, "pronunciation"])
            df.at[idx, "pronunciation"] = yomi_result

        # 正規化（英語→カナ、ひら→カタ、記号除去など）
        df["pronunciation"] = df["pronunciation"].apply(self.text_analyzer.format_kana)

        # 空の発音を除外
        return df[df["pronunciation"].str.len() > 0]

    def _process_row_to_parody_words(self, row: pd.Series) -> list[ParodyWord]:
        """
        行データからParodyWordのリストを生成する。
        
        Args:
            row: DataFrameの行データ。最低限surface列をもつ。
            
        Returns:
            ParodyWordのリスト
        """
        parody_words: list[ParodyWord] = []

        # pronunciationが無い/NAのときはsurfaceから読みを推定
        pronunciation = row.get("pronunciation", "").lower()
        if not pronunciation or pronunciation == "na":
            surface = row.get("surface", "").lower()
            row["pronunciation"] = self.text_analyzer.get_yomi(surface)

        
        # バリエーション（モーラ列の置換パターン等）
        pronunciation_variations = self.text_analyzer.yomi_to_variation(row["pronunciation"])

        for p in pronunciation_variations:
            parody_word: ParodyWord = {
                "surface": str(row.get("surface", "")),
                "pronunciation": p,
                "kana": str(row["pronunciation"]),
                "id": str(row.get("id", row.name)),
                "original": str(row.get("original", row.get("surface", ""))),
            }
            parody_words.append(parody_word)
            
        return parody_words

    def parse_tidy(self, csv_text: str, where: str = "") -> dict[int, list[ParodyWord]]:
        """
        JS: loadDatabaseCsvText(text, query_str)
        pandasを使ってシンプルに実装
        """

        # pandasでCSVを読み込み
        df = pd.read_csv(StringIO(csv_text))

        # 条件適用（where句がある場合）
        if where:
            # pandasのquery機能を使用してフィルタリング
            where_pandas = convert_where_query_to_pandas(where)
            df = df.query(where_pandas)
            if df.empty:
                return {}

        # pronunciation列の前処理
        df = self._prepare_pronunciation_column(df)
        
        if df.empty:
            return {}

        # 変形パターン展開 - applyを使用して一括処理
        all_parody_words = df.apply(self._process_row_to_parody_words, axis=1)

        # 結果をlengthごとに分類
        resultdb: dict[int, list[ParodyWord]] = {}
        
        for parody_word_list in all_parody_words:
            for parody_word in parody_word_list:
                length = len(parody_word["pronunciation"])
                if length not in resultdb:
                    resultdb[length] = []
                resultdb[length].append(parody_word)

        return resultdb

    # ---- plain text -> tidy CSV -> parse ----
    @staticmethod
    def _plain_to_csv(plain_text: str) -> str:
        """
        JS plainToCsv:
          1列目: original（タイトル）
          2列目以降: surface 候補
          1列のみなら original=surface として1行化
        出力 CSV: header 行 + 各行: id,original,surface,pronunciation
        """
        header = ["id", "original", "surface", "pronunciation"]
        lines = re.split(r"\r\n|\n", plain_text)
        # コメント除去・ゼロ幅スペース除去
        lines = [re.sub(r"#.*$", "", ln) for ln in lines]
        lines = [ln.replace("\u200b", "") for ln in lines]
        # カンマ分割
        parts = [ln.split(",") for ln in lines]
        # 無効行除去
        parts = [p for p in parts if len(p) > 0 and (p[0] or "").strip()]

        csv_rows: list[list[str]] = []
        for i, row in enumerate(parts):
            if len(row) == 1:
                v = row[0].strip()
                csv_rows.append([str(i), v, v, v])
            else:
                title = row[0].strip()
                for cand in row[1:]:
                    cand_stripped = cand.strip()
                    if cand_stripped:
                        csv_rows.append([str(i), title, cand_stripped, cand_stripped])

        # join
        out_lines = [",".join(header)]
        out_lines += [",".join(r) for r in csv_rows]
        return "\n".join(out_lines)

    def parse_plain(self, text: str) -> dict[int, list[ParodyWord]]:
        """
        JS loadDatabaseText(text) の簡潔版:
        - プレーンを CSV にしてから parse_tidy を適用
        """
        csv_text = self._plain_to_csv(text)
        return self.parse_tidy(csv_text, where="")
