# 移植元: frontend/src/lib/wordList.js
"""wordList.js からの移植(ロジック無改変)。

Parser: where式(``key = value`` / ``!=`` / and / or / 括弧)の評価とフィルタ。
WordList: CSV/plain テキストから、発音バリエーションの長さをキーにした単語DBを構築する。

デッドコード(loadDatabaseTextWithMeCab、loadDatabaseText 内の return 後の到達不能
コード)は移植しない。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

Word = dict[str, Any]
ResultDB = dict[int, list[Word]]


class Parser:
    """wordList.js の Parser()。"""

    @staticmethod
    def _tokenize(query_str: str) -> list[str]:
        query_str = re.sub(r"!=|=|\(|\)", lambda m: " " + m.group(0) + " ", query_str)
        query_str = query_str.strip()
        return re.split(r"\s+", query_str)

    def _expression(
        self,
        obj: Any,
        query: list[str],
        i: int,
        check_func: Callable[[list[str], int, Any], Any],
    ) -> Any:
        """[結果, 消費した次のインデックス] を返す。エラー時は -1。"""
        if i >= len(query):
            return -1

        r = self._factor(obj, query, i, check_func)
        if r == -1:
            return -1

        result = r[0]
        i = r[1]

        while i < len(query):
            if query[i] == ")":
                break
            if query[i] != "or" and query[i] != "and":
                return -1

            r2 = self._factor(obj, query, i + 1, check_func)
            if r2 == -1:
                return -1

            if query[i] == "or":
                result = result or r2[0]
            else:
                result = result and r2[0]

            i = r2[1]

        return [result, i]

    def _factor(
        self,
        obj: Any,
        query: list[str],
        i: int,
        check_func: Callable[[list[str], int, Any], Any],
    ) -> Any:
        if query[i] == "(":
            r = self._expression(obj, query, i + 1, check_func)
            if r == -1:
                return -1
            if query[r[1]] == ")":
                return [r[0], r[1] + 1]
            else:
                return -1
        elif i < len(query) - 2 and (query[i + 1] == "=" or query[i + 1] == "!="):
            r = check_func(query, i, obj)
            if r == -1:
                return -1
            return [r, i + 3]
        else:
            return -1

    @staticmethod
    def _get_keys(query: list[str]) -> list[str]:
        result: list[str] = []
        for i in range(1, len(query) - 1):
            if query[i] == "=" or query[i] == "!=":
                if query[i - 1] not in result:
                    result.append(query[i - 1])
        return result

    def eval(self, query_str: str, obj: dict[str, Any]) -> Any:
        query = self._tokenize(query_str)

        def check_func(query: list[str], i: int, obj: dict[str, Any]) -> Any:
            if query[i + 1] == "=":
                return obj[query[i]] == query[i + 2]
            elif query[i + 1] == "!=":
                return obj[query[i]] != query[i + 2]
            else:
                return -1

        result = self._expression(obj, query, 0, check_func)
        return -1 if result == -1 else result[0]

    def filter(
        self, query_str: str, header: list[str], dataframe: list[list[str]]
    ) -> list[list[str]] | bool:
        query = self._tokenize(query_str)
        keys = self._get_keys(query)
        key_to_index: dict[str, int] = {}
        for k in keys:
            index = header.index(k) if k in header else -1
            if index == -1:
                return False
            key_to_index[k] = index

        def check_func(query: list[str], i: int, obj: list[str]) -> Any:
            if query[i + 1] == "=":
                index = key_to_index[query[i]]
                return obj[index] == query[i + 2]
            elif query[i + 1] == "!=":
                index = key_to_index[query[i]]
                return obj[index] != query[i + 2]
            else:
                return -1

        result: list[list[str]] = []
        for obj in dataframe:
            r = self._expression(obj, query, 0, check_func)
            if r != -1 and r[0]:
                result.append(obj)
        return result


class WordList:
    """wordList.js の WordList(textAnalyzer)。"""

    def __init__(self, text_analyzer: Any) -> None:
        self.text_analyzer = text_analyzer
        self._word_list: dict[str, ResultDB] = {}

    def parse_tidy(self, text: str, query_str: str = "") -> ResultDB:
        return self._load_database_csv_text(text, query_str)

    def parse_plain(self, text: str) -> ResultDB:
        return self._load_database_text(text)

    def _load_database_csv_text(self, text: str, query_str: str) -> ResultDB:
        text = re.sub(r"\s*,\s*", ",", text)
        lines = re.split(r"\r\n|\n|\r", text)
        header = lines[0].split(",")
        df: list[list[str]] = []
        for i in range(1, len(lines)):
            df.append(lines[i].split(","))

        parser = Parser()
        if query_str:
            filtered = parser.filter(query_str, header, df)
            filtered_df: list[list[str]] = filtered if isinstance(filtered, list) else []
        else:
            filtered_df = df

        h2i: dict[str, int] = {}
        for i in range(len(header)):
            h2i[header[i]] = i

        # JSでは pronunciation 列が無いCSVでも v[h2i["pronunciation"]] が undefined に
        # なり surface 代用にフォールバックする(nations.csv等)。列欠落のみ再現し、
        # 行が header より短いケースはJSも落ちるので救済しない
        p_idx = h2i.get("pronunciation")
        pronunciations: list[str] = []
        for v in filtered_df:
            p = v[p_idx] if p_idx is not None and p_idx < len(v) else None
            if (not p) or p == "NA" or p == "na":
                p = v[h2i["surface"]]
            pronunciations.append(p)

        # kanjiがあるときだけtokenizerにかける
        kanji_pronunciation: list[str] = []
        kanji_pronunciation_id: list[int] = []
        for i in range(len(pronunciations)):
            p = pronunciations[i]
            if re.search(r"[一-龠]", p):
                kanji_pronunciation.append(p)
                kanji_pronunciation_id.append(i)

        if len(kanji_pronunciation) > 0:
            yomi = self.text_analyzer.get_yomi(kanji_pronunciation)
            for i in range(len(kanji_pronunciation_id)):
                index = kanji_pronunciation_id[i]
                pronunciations[index] = yomi[i]

        pronunciations = [self.text_analyzer.format_kana(v) for v in pronunciations]

        resultdb: ResultDB = {}
        for i in range(len(filtered_df)):
            line = filtered_df[i]
            obj: dict[str, Any] = {}
            for k in range(len(header)):
                obj[header[k]] = line[k]
            obj["pronunciation"] = pronunciations[i]
            if not obj["pronunciation"]:
                continue

            pvariations = self.text_analyzer.yomi_to_variation(obj["pronunciation"])
            for p in pvariations:
                plen = len(p)
                if plen not in resultdb:
                    resultdb[plen] = []
                resultdb[plen].append(
                    {
                        "surface": obj["surface"],
                        "pronunciation": p,
                        "kana": obj["pronunciation"],
                        "id": obj["id"],
                        "original": obj["original"],
                    }
                )
        return resultdb

    @staticmethod
    def _plain_to_csv(text: str) -> str:
        header = [["id", "original", "surface", "pronunciation"]]
        raw_lines = re.split(r"\r\n|\n", text)
        stripped = [re.sub(r"#.*$", "", v) for v in raw_lines]  # #以降をコメントアウト
        stripped = [v.replace("​", "") for v in stripped]  # ゼロ幅スペース除去
        split_lines = [v.split(",") for v in stripped]  # カンマでスプリット
        lines = [v for v in split_lines if len(v) > 0 and v[0]]  # 不正な行を削除

        csvlines: list[list[str]] = []
        for i in range(len(lines)):
            v = lines[i]
            if len(v) == 1:
                csvlines.append([str(i), v[0], v[0], v[0]])
            else:
                for j in range(1, len(v)):
                    if v[j]:
                        csvlines.append([str(i), v[0], v[j], v[j]])

        db = header + csvlines
        return "\n".join(",".join(row) for row in db)

    def _load_database_text(self, text: str) -> ResultDB:
        csvtext = self._plain_to_csv(text)
        return self._load_database_csv_text(csvtext, "")
