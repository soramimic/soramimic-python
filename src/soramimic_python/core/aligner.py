from typing import TypedDict, Callable

import editdistance as ed

class BaseAlignedPair(TypedDict):
    target: tuple[str, ...]
    reference: tuple[str, ...]

class BaseAligner:
    def __init__(self, cost_func: Callable[[tuple[str, ...], tuple[str, ...]], float] | None = None,
                 pair_length_patterns: set[tuple[int, int]] | None = None):
        if cost_func:
            self.cost_func = cost_func
        else:
            self.cost_func = lambda x, y: ed.eval(x, y)
        
        if pair_length_patterns:
            self.pair_length_patterns = pair_length_patterns
        else:
            self.pair_length_patterns = {(1,1), (1,0), (0,1)}
        self.memo = {}

    def align(self, target_list: tuple[str, ...], reference_list: tuple[str, ...]) -> tuple[float, list[BaseAlignedPair]]:
        if (target_list, reference_list) in self.memo:
            return self.memo[(target_list, reference_list)]
        
        if not target_list and not reference_list:
            return 0, []
        
        cost_and_results = []
        for target_length, reference_length in self.pair_length_patterns:
            if len(target_list) >= target_length and len(reference_list) >= reference_length:
                first_cost = self.cost_func(target_list[:target_length], reference_list[:reference_length])
                first_result = [BaseAlignedPair(target=target_list[:target_length], reference=reference_list[:reference_length])]
                other_cost, other_result = self.align(target_list[target_length:], reference_list[reference_length:])
                cost = first_cost + other_cost
                result = first_result + other_result
                if cost == float("inf"):
                    continue

                cost_and_results.append((cost, result))

        if not cost_and_results:
            min_cost, min_result = float("inf"), [BaseAlignedPair(target=target_list, reference=reference_list)]
            self.memo[(target_list, reference_list)] = (min_cost, min_result)
            return min_cost, min_result
        min_cost, min_result = min(cost_and_results, key=lambda x: x[0])
        self.memo[(target_list, reference_list)] = (min_cost, min_result)
        return min_cost, min_result


if __name__ == "__main__":
    # Example usage
    def kanji_cost_func(target: tuple[str, ...], reference: tuple[str, ...]) -> float:
        target_str = "".join(target)
        reference_str = "".join(reference)
        zero_cost_pair = [
            ("長谷", "はせ"),
            ("川", "かわ"),
            ("川", "がわ"),
            ("庭", "にわ"),
            ("「", ""),
        ]
        if (target_str, reference_str) in zero_cost_pair:
            return 0.0 + 0.0001*len(target)*len(reference)
        else:
            return ed.eval(target, reference) + 0.0001*len(target)*len(reference)
    #aligner = BaseAligner(kanji_cost_func, [(2,2),(1,2),(1,0),(0,1),(1,1)])
    #print(aligner.align(tuple(jamorasep.parse("「庭」には２羽鶏がいる")), tuple(jamorasep.parse("にわにはにわにわとりがいる"))))
    aligner = RubiAligner()
    print(aligner.align("庭には2羽鶏がいる", "ニワニワニワニワトリガイル"))
    print(aligner.align("庭には2羽鶏がいる", "ニワニワニワニワトリガイル")[1][0].target)
