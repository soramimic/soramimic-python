import re
from collections.abc import Callable
from io import StringIO
from typing import Any, TypedDict

import pandas as pd


class ParodyWord(TypedDict, total=False):
    id: str
    surface: str
    pronunciation: str
    kana: str
    original: str


class Parser:
    """
    JS Parser() を Python へ移植。
    - トークン: !=, =, (, ), AND/OR（小文字 'and' / 'or'）
    - 式: (factor ( (and|or) factor )*)
    - factor: key (=|!=) value | '(' expression ')'
    - eval: dict に対して評価
    - filter: ヘッダ付き2次元配列に対してフィルタ
    """

    @staticmethod
    def _tokenize(query_str: str) -> list[str]:
        # '!=', '=', '(', ')' を前後にスペース → ホワイトスペース split
        s = re.sub(r"(!=|=|\(|\))", r" \1 ", query_str)
        s = s.strip()
        return re.split(r"\s+", s) if s else []

    def _expression(
        self,
        obj: Any,
        query: list[str],
        i: int,
        check_func: Callable[[list[str], int, Any], Any],
    ) -> tuple[bool, int] | int:
        if i >= len(query):
            return -1

        r = self._factor(obj, query, i, check_func)
        if r == -1:
            return -1

        assert isinstance(r, tuple), "r should be tuple when not -1"
        result, i = r

        while i < len(query):
            if query[i] not in ("or", "and"):
                break  # JS は -1 を返していたが、式終端で抜けるのが自然
            r2 = self._factor(obj, query, i + 1, check_func)
            if r2 == -1:
                return -1
            assert isinstance(r2, tuple), "r2 should be tuple when not -1"
            right, i = r2
            if query[i - 1] == "or":
                result = bool(result) or bool(right)
            else:
                result = bool(result) and bool(right)

        return bool(result), i

    def _factor(
        self,
        obj: Any,
        query: list[str],
        i: int,
        check_func: Callable[[list[str], int, Any], Any],
    ) -> tuple[bool, int] | int:
        if i >= len(query):
            return -1

        if query[i] == "(":
            r = self._expression(obj, query, i + 1, check_func)
            if r == -1:
                return -1
            assert isinstance(r, tuple), "r should be tuple when not -1"
            val, j = r  # j は次のトークン位置
            if j < len(query) and query[j] == ")":
                return bool(val), j + 1
            return -1

        # key (=|!=) value  の3トークンが必要
        if i < len(query) - 2 and query[i + 1] in ("=", "!="):
            res = check_func(query, i, obj)
            if res == -1:
                return -1
            return bool(res), i + 3

        return -1

    @staticmethod
    def _get_keys(query: list[str]) -> list[str]:
        result: list[str] = []
        for i in range(1, len(query) - 1):
            if query[i] in ("=", "!="):
                key = query[i - 1]
                if key not in result:
                    result.append(key)
        return result

    # ---------- public ----------
    def eval(self, query_str: str, obj: dict[str, Any]) -> bool:
        query = self._tokenize(query_str)

        def check(q: list[str], i: int, o: dict[str, Any]) -> bool | int:
            key, op, val = q[i], q[i + 1], q[i + 2]
            if op == "=":
                return o.get(key) == val
            if op == "!=":
                return o.get(key) != val
            return -1

        r = self._expression(obj, query, 0, check)
        if r == -1:
            return False
        return bool(r[0])  # type: ignore[index]

    def filter(
        self,
        query_str: str,
        header: list[str],
        dataframe: list[list[str]],
    ) -> list[list[str]]:
        query = self._tokenize(query_str)
        keys = self._get_keys(query)

        key_to_index: dict[str, int] = {}
        for k in keys:
            try:
                key_to_index[k] = header.index(k)
            except ValueError:
                # 参照キーがヘッダにない場合は空結果（JS は console.log のみ）
                return []

        def check(q: list[str], i: int, row: list[str]) -> bool | int:
            key, op, val = q[i], q[i + 1], q[i + 2]
            idx = key_to_index[key]
            if op == "=":
                return row[idx] == val
            if op == "!=":
                return row[idx] != val
            return -1

        out: list[list[str]] = []
        for row in dataframe:
            r = self._expression(row, query, 0, check)
            if r != -1 and r[0]:  # type: ignore[index]
                out.append(row)
        return out


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
        self._parser = Parser()

    # ---- core helpers ----
    @staticmethod
    def _has_kanji(s: str) -> bool:
        return re.search(r"[一-龠]", s) is not None

    @staticmethod
    def _clean_csv_text(text: str) -> str:
        # カンマ前後の空白削除（, の左右の \s* を消す）
        return re.sub(r"\s*,\s*", ",", text)

    # ---- tidy CSV text loader ----
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
            try:
                where_pandas = convert_where_query_to_pandas(where)
                df = df.query(where_pandas)
                if df.empty:
                    return {}
            except Exception:
                # クエリが無効な場合は空結果を返す
                return {}

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
        df = df[df["pronunciation"].str.len() > 0]

        # 変形パターン展開
        resultdb: dict[int, list[ParodyWord]] = {}

        for idx, row in df.iterrows():
            # バリエーション（モーラ列の置換パターン等）
            pvars = self.text_analyzer.yomi_to_variation(row["pronunciation"])

            for p in pvars:
                length = len(p)
                parody_word: ParodyWord = {
                    "surface": str(row.get("surface", "")),
                    "pronunciation": p,
                    "kana": str(row["pronunciation"]),
                    "id": str(row.get("id", idx)),
                    "original": str(row.get("original", row.get("surface", ""))),
                }

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
