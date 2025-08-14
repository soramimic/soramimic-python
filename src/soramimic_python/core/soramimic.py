class SoramimiMaker:
    def __init__(self, kana_similarity, text_analyzer):
        self.kana_similarity = kana_similarity
        self.text_analyzer = text_analyzer

    def _assign_default_parameter(self, parameters):
        default_parameter_values = {
            "repeat": 100,
            "splitter": "/",
            "duplicate": True,
            "same_phrase_break_reward": 1,
            "word_number_penalty": 1,
            "length": 1,
        }
        default_parameter_values.update(parameters)
        return default_parameter_values

    def _ld(self, s, t, kana_dist):
        if not s or not t:
            return float("inf")
        if len(s) != len(t):
            return float("inf")
        score = 0
        for i in range(len(s)):
            if s[i] in kana_dist and t[i] in kana_dist:
                score += kana_dist[s[i]][t[i]]
            else:
                return float("inf")
        return score

    def _get_similar_word(self, word_list, target, kana_dist, length=1):
        tmp = self.text_analyzer.syllable_to_variation(target)
        candidates = {}
        for c in tmp:
            if len(c) not in word_list:
                continue
            candidates.setdefault(len(c), []).append(c)

        words = {}
        for i in candidates:
            for w in word_list[i]:
                w["sim"] = float("inf")
                for c in candidates[i]:
                    d = (
                        self._ld(c, w["pronunciation"], kana_dist)
                        / int(i)
                        * len(target)
                    )
                    w["sim"] = min(d, w["sim"])
                if w["id"] in words and w["sim"] > words[w["id"]]["sim"]:
                    continue
                words[w["id"]] = w

        words_list = list(words.values())
        words_list.sort(key=lambda x: x["sim"])
        return words_list

    def _get_min(self, array, get_value):
        min_val = float("inf")
        content = None
        for v in array:
            val = get_value(v)
            if val < min_val:
                content = v
                min_val = val
        return content

    class _Memo:
        def __init__(self):
            self.m = {}

        def set(self, start, end, value):
            self.m.setdefault(start, {})[end] = value

        def get(self, start, end, dft=None):
            return self.m.get(start, {}).get(end, dft)

        def has(self, start, end):
            return start in self.m and end in self.m[start]

    def _convert(self, tokens, get_similar_word_func, used_words, param=None):
        if param is None:
            param = {}

        is_duplicate = param["duplicate"]
        same_phrase_break = param["same_phrase_break_reward"]
        words_num = param["word_number_penalty"]

        used = used_words
        target = [v["pronunciation"] for v in tokens]
        phrase_breaks = [
            j
            for j, v in enumerate(tokens)
            if j == 0 or v["phrase"] != tokens[j - 1]["phrase"]
        ]

        memo = self._Memo()
        memo.set(0, 0, [0, []])

        def dp(s, t):
            if memo.has(s, t):
                return memo.get(s, t)
            if s == t:
                memo.set(s, t, [0, []])
                return memo.get(s, t)

            results = []
            for i in range(s, t):
                subtarget = target[i:t]
                similar_words = get_similar_word_func(subtarget)
                if not similar_words:
                    continue

                r = dp(s, i)
                if not r or r[0] == float("inf"):
                    continue

                prev_score, prev_words = r
                current_used = [w["id"] for w in prev_words]

                new_word = None
                if is_duplicate:
                    new_word = dict(similar_words[0])
                else:
                    for w in similar_words:
                        if w["id"] not in used and w["id"] not in current_used:
                            new_word = dict(w)
                            break

                if not new_word:
                    continue

                new_word["original_kana"] = "".join(subtarget)
                new_word["score"] = new_word["sim"]

                if t in phrase_breaks:
                    new_word["score"] -= same_phrase_break * 1
                new_word["period"] = [i, t]

                new_score = prev_score + new_word["score"] + words_num
                new_words = prev_words + [new_word]
                results.append([new_score, new_words])

            if not results:
                result = [float("inf"), []]
                memo.set(s, t, result)
                return result

            result = self._get_min(results, lambda v: v[0])
            memo.set(s, t, result)
            return result

        return dp(0, len(target))

    def generate(self, phrases, word_list, parameter, update_func, end_func):
        param = self._assign_default_parameter(parameter)

        def gs(target):
            kana_dist = self.kana_similarity.get_kana_similarity(param)
            joined_target = "".join(target)
            if not hasattr(gs, "memo"):
                gs.memo = {}
            if joined_target in gs.memo:
                return gs.memo[joined_target]
            result = self._get_similar_word(word_list, target, kana_dist, 100)
            gs.memo[joined_target] = result
            return result

        tokens_list = self.text_analyzer.tokenize_together(phrases)
        tokenized_phrases = [
            self.text_analyzer.get_yomi_and_phrase_break(v) for v in tokens_list
        ]

        used_words = []
        results = []

        def convert_line(i):
            if i >= len(tokenized_phrases):
                if end_func:
                    end_func(results)
            else:
                tokens = tokenized_phrases[i]
                raw_result = self._convert(tokens, gs, used_words, param)
                result = []
                if raw_result:
                    for v in raw_result[1]:
                        original_surface = "".join(
                            t["surface_form"]
                            for t in tokens[v["period"][0] : v["period"][1]]
                        )
                        v["original_surface"] = original_surface
                        result.append(v)
                if update_func:
                    update_func(result, i, tokenized_phrases)
                used_words.extend(v["id"] for v in result)
                results.append(result)
                convert_line(i + 1)

        convert_line(0)
        return results
