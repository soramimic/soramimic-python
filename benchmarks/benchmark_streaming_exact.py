#!/usr/bin/env python3
"""本番相当の歌詞・CSVでgenerate_from_tokensの時間/RSS/出力署名を測る。

例:
  uv run --extra mecab python benchmarks/benchmark_streaming_exact.py \
    --label akatombo-stations --lyrics /path/akatombo_lyrics.txt \
    --wordlist /path/stations.csv --warmups 1 --runs 3

同じコマンドを変更前revisionと変更後revisionの環境で実行し、``output_sha256``、
``id_count``、``score_total``、``filler_count``が一致することを確認する。
``peak_rss_kib``はプロセス全体（辞書・MeCab・CSV DBを含む）のru_maxrss。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import statistics
import time
from pathlib import Path
from typing import Any

from soramimic import create_soramimic, load_default_data, scale_similarity
from soramimic.kana_to_syllable import syllable_variations
from soramimic.tokenizers.mecab import MeCabTokenizer


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--lyrics", type=Path, action="append", required=True)
    parser.add_argument("--wordlist", type=Path, required=True)
    parser.add_argument("--where", default="")
    parser.add_argument("--warmups", type=int, default=0)
    parser.add_argument("--runs", type=int, default=1)
    return parser.parse_args()


def _max_variation_units(tokenized_phrases: list[list[dict[str, Any]]]) -> int | None:
    longest = 0
    for tokens in tokenized_phrases:
        longest = max(
            longest,
            sum(
                max(
                    (len(units) for units, _ in syllable_variations(token["pronunciation"])),
                    default=0,
                )
                for token in tokens
            ),
        )
    return longest + 2 if longest else None


def _signature(results: list[list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [
        [
            {
                "id": word.get("id"),
                "score": word["score"],
                "filler": bool(word.get("filler")),
            }
            for word in line
        ]
        for line in results
    ]
    encoded = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    words = [word for line in rows for word in line]
    return {
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "id_count": sum(word["id"] is not None for word in words),
        "score_total": sum(word["score"] for word in words),
        "filler_count": sum(word["filler"] for word in words),
    }


def main() -> None:
    args = _arguments()
    started = time.perf_counter()
    phrases = [
        line.strip()
        for lyrics in args.lyrics
        for line in lyrics.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    data = load_default_data(similarity="monotie")
    ratio = 0.8
    tokenizer = MeCabTokenizer()
    app = create_soramimic(
        **{
            **data,
            "vowel_similarity": scale_similarity(data["vowel_similarity"], 2 * ratio),
            "consonant_similarity": scale_similarity(data["consonant_similarity"], 2 * (1 - ratio)),
        },
        tokenize_sentenses=tokenizer.tokenize,  # type: ignore[arg-type]
        get_yomi=tokenizer.get_yomi,
    )
    tokens_list = app.text_analyzer.tokenize_together(phrases)
    tokenized_phrases = [app.text_analyzer.get_yomi_and_phrase_break(v) for v in tokens_list]

    parse_started = time.perf_counter()
    db = app.word_list.parse_tidy(
        args.wordlist.read_text(encoding="utf-8"),
        args.where,
        max_units=_max_variation_units(tokenized_phrases),
    )
    parse_seconds = time.perf_counter() - parse_started
    params = {
        "DUPLICATE": False,
        "VOWEL_RATIO": ratio,
        "VARIATION_COST": 20 * ratio,
        "SAME_PHRASE_BREAK_REWARD": 0,
        "MID_PHRASE_BREAK_PENALTY": 20,
        "WORD_NUMBER_PENALTY": 20,
    }

    result: list[list[dict[str, Any]]] = []
    for _ in range(args.warmups):
        result = app.soramimi_maker.generate_from_tokens(tokens_list, db, params)

    durations = []
    signatures = []
    for _ in range(args.runs):
        generate_started = time.perf_counter()
        result = app.soramimi_maker.generate_from_tokens(tokens_list, db, params)
        durations.append(time.perf_counter() - generate_started)
        signatures.append(_signature(result))
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise RuntimeError("repeated runs produced different outputs")

    print(
        json.dumps(
            {
                "label": args.label,
                "mode": "warm" if args.warmups else "cold",
                "lyrics": [str(path) for path in args.lyrics],
                "wordlist": str(args.wordlist),
                "line_count": len(phrases),
                "db_entries": sum(len(bucket) for bucket in db.values()),
                "parse_seconds": parse_seconds,
                "generate_seconds": durations,
                "generate_median_seconds": statistics.median(durations),
                "total_seconds": time.perf_counter() - started,
                "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                **signatures[0],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
