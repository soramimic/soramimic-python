from soramimic_python.core.pronouncer.base import BasePronouncer

FIRST_TEN = ["イチ", "ニ", "サン", "ヨン", "ゴ", "ロク", "ナナ", "ハチ", "キュウ"]
OTHER_TENS = [
    "ジュウ",
    "ニジュウ",
    "サンジュウ",
    "ヨンジュウ",
    "ゴジュウ",
    "ロクジュウ",
    "ナナジュウ",
    "ハチジュウ",
    "キュウジュウ",
]
HUNDRED = "ヒャク"

def _num_to_japanese(number):
    # 100の位の数の求め方
    n = number // 100
    t = [FIRST_TEN[n-1], HUNDRED] if n > 2 else []
    
    # 10の位の数の求め方
    n = (number // 10) % 10
    t += [OTHER_TENS[n-1]] if n > 0 else []
    
    # 1の位の数の求め方
    n = number % 10
    t += FIRST_TEN[n-1] if n > 0 else []

    return ''.join(t)

class NumberPronouncer(BasePronouncer):
    def get_match_pattern_with_tag(self, tag: str) -> str:
        return fr'(?P<{tag}>\p{{Nd}}+)'

    def pronounce(self, text: str) -> str:
        return _num_to_japanese(int(text))