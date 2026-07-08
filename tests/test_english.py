"""english の代表ケースのテスト。"""

from __future__ import annotations

from typing import Any

from soramimic.english import Apostrophe, English


def test_apostrophe_roundtrip() -> None:
    ap = Apostrophe()
    assert ap.to_string("don't") == "donAPOSTROPHE t".replace(" ", "")
    assert ap.to_sign("donAPOSTROPHEt") == "don't"
    assert ap.remove_string("donAPOSTROPHEt") == "dont"
    # 全角アポストロフィも退避される
    assert ap.to_string("don’t") == "donAPOSTROPHEt"


def test_is_fullmatch() -> None:
    eng = English({}, {})
    assert English.is_fullmatch("cat") is True
    assert English.is_fullmatch("don't") is True
    assert English.is_fullmatch("ネコ") is False
    assert English.is_fullmatch("cat2") is False
    assert isinstance(eng, English)


def test_to_kana_uses_dictionary(default_data: dict[str, Any]) -> None:
    eng = English(default_data["english_dict"], default_data["roman_tree"])
    # 実データ辞書を用いた変換がカタカナを返すこと(値は JS と一致確認済み)
    assert eng.to_kana("cat") == "キャット"
    assert eng.to_kana("dog") == "ドッグ"
