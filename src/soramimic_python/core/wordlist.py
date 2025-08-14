import re
from collections.abc import Callable
from typing import Any


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


class WordList:
    """
    JS WordList(textAnalyzer) を Python へ移植。
    - parseTidy: tidy CSV テキストと where 句（任意）を受けて {長さ: [語…]} を返す
    - parsePlain: プレーンテキストを CSV に変換してから同上
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

    @staticmethod
    def _split_csv_lines(text: str) -> tuple[list[str], list[list[str]]]:
        lines = re.split(r"\r\n|\n|\r", text)
        if not lines or not lines[0]:
            return [], []
        header = lines[0].split(",")
        df: list[list[str]] = []
        for line in lines[1:]:
            if line == "":
                continue
            df.append(line.split(","))
        return header, df

    # ---- tidy CSV text loader ----
    def parseTidy(
        self, csv_text: str, where: str = ""
    ) -> dict[int, list[dict[str, Any]]]:
        """
        JS: loadDatabaseCsvText(text, query_str)
        """
        text = self._clean_csv_text(csv_text)
        header, df = self._split_csv_lines(text)
        if not header:
            return {}

        # 条件適用
        if where:
            df = self._parser.filter(where, header, df)

        # ヘッダ index
        h2i = {h: idx for idx, h in enumerate(header)}

        # pronunciation が無い/NA のときは surface を採用
        pronunciations: list[str] = []
        for row in df:
            p = row[h2i.get("pronunciation", -1)] if "pronunciation" in h2i else ""
            if not p or p.lower() == "na":
                p = row[h2i["surface"]]
            pronunciations.append(p)

        # かな推定（漢字を含む行だけ個別に get_yomi を呼び出し）
        kanji_indices: list[int] = [
            i for i, p in enumerate(pronunciations) if self._has_kanji(p)
        ]
        if kanji_indices:
            # 各文字列に対して個別にget_yomiを呼び出し
            for idx in kanji_indices:
                yomi_result = self.text_analyzer.get_yomi(pronunciations[idx])
                pronunciations[idx] = yomi_result

        # 正規化（英語→カナ、ひら→カタ、記号除去など）
        pronunciations = [self.text_analyzer.format_kana(p) for p in pronunciations]

        # 変形パターン展開
        resultdb: dict[int, list[dict[str, Any]]] = {}
        for i, row in enumerate(df):
            obj = {h: row[h2i[h]] for h in header if h in h2i and h2i[h] < len(row)}

            kana_norm = pronunciations[i]
            if not kana_norm:
                continue

            # バリエーション（モーラ列の置換パターン等）
            pvars = self.text_analyzer.yomi_to_variation(kana_norm)
            for p in pvars:
                L = len(p)
                resultdb.setdefault(L, []).append(
                    {
                        "surface": obj.get("surface", ""),
                        "pronunciation": p,
                        "kana": kana_norm,
                        "id": obj.get("id", str(i)),
                        "original": obj.get("original", obj.get("surface", "")),
                    }
                )

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

    def parsePlain(self, text: str) -> dict[int, list[dict[str, Any]]]:
        """
        JS loadDatabaseText(text) の簡潔版:
        - プレーンを CSV にしてから parseTidy を適用
        """
        csv_text = self._plain_to_csv(text)
        return self.parseTidy(csv_text, where="")
