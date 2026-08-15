# Streaming exact benchmark (2026-08-15)

## Scope and method

`DUPLICATE=false` の変更前固定rev `a1e73df46f9ef87d1aef532a47bfe9b638141e66`
と本変更を、別linked worktree・別venv・別プロセスで比較した。
`benchmarks/benchmark_streaming_exact.py` を使い、soramimic-video同梱の実歌詞を
MeCabでtokenizeし、実CSVを`parse_tidy(max_units=歌詞側上限)`してから
`generate_from_tokens()`を実行した。パラメータは動画生成のバランス既定値
（VOWEL_RATIO=0.8、VARIATION_COST=16、DUPLICATE=false等）と同じ。

- cold: DB構築後、生成を1回測定
- warm: DB構築・生成1回の予熱後、生成3回の中央値
- peak RSS: `/usr/bin/time -v` と `resource.getrusage().ru_maxrss` の一致値。
  辞書、MeCab、CSV DB、予熱を含むプロセス全体のhigh-water mark
- 出力比較: 各wordの`id`・`score`・`filler`をcanonical JSONにしてSHA-256化。
  併せてID数、score合計、filler数を比較

環境: Linux 7.0.0-28-generic、AMD Ryzen 7 5700X (8C/16T)、RAM 62 GiB、
Python 3.12.3。時刻やOS page cacheを完全固定したmicrobenchmarkではないため、
時間の小差よりRSSと出力一致を主眼にする。

## Results

| song / word list | mode | entries | old generate | streaming generate | delta | old peak RSS | streaming peak RSS | delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 赤とんぼ / stations | cold | 25,032 | 0.795 s | 0.782 s | -1.5% | 172.6 MiB | 109.9 MiB | -36.3% |
| 赤とんぼ / stations | warm | 25,032 | 0.875 s | 0.795 s | -9.1% | 203.3 MiB | 115.2 MiB | -43.3% |
| 赤とんぼ / gimukyoiku | cold | 23,282 | 0.585 s | 0.732 s | +25.1% | 128.0 MiB | 91.5 MiB | -28.5% |
| 赤とんぼ / gimukyoiku | warm | 23,282 | 0.639 s | 0.751 s | +17.5% | 163.4 MiB | 106.7 MiB | -34.7% |
| Lemon（40行） / stations | cold | 25,538 | 9.154 s | 12.064 s | +31.8% | 1,651.5 MiB | 123.1 MiB | -92.5% |
| Lemon（40行） / stations | warm | 25,538 | 11.248 s | 12.016 s | +6.8% | 1,813.9 MiB | 124.2 MiB | -93.2% |

warmのRSSは予熱を含むhigh-water markなので、旧経路ではGS候補cache等の大きな一時
オブジェクトが解放後もallocatorに保持される影響を含む。streaming経路は固定長256 entry
の列和bufferだけを使うため、曲が長くなっても候補cacheに比例してRSSが増えなかった。

## Output equivalence

全6比較で、変更前後のID列・各word score・filler flagのSHA-256、ID数、score合計、
filler数が一致した。

| song / word list | output SHA-256 | ID count | score total | filler count |
|---|---|---:|---:|---:|
| 赤とんぼ / stations | `3ac9793a10372d5bc7faa6f349a59b924460efd174bbb4d0acb1600874a56a7a` | 8 | 203.86098221690762 | 0 |
| 赤とんぼ / gimukyoiku | `4c206fe0a6ce4b6437715532748fabcd6e436b54114d259de17fcc83e48feb87` | 9 | 231.80856850202315 | 0 |
| Lemon / stations | `c0a119b31cbae0a9dc5e305645a8f9d431b00d84cc25da3e8cb197fda623ec24` | 184 | 5950.420288439606 | 0 |

fillerが実際に混在・枯渇するケースはunit testで別途固定した。大規模実データ3組では
候補が十分だったためfiller数は0で一致した。

## Trade-off

短い曲×gimukyoikuと長いLemonの生成時間は一部悪化した。一方、最も厳しい長曲ケースの
peak RSSは約1.8 GiBから約124 MiBへ93%減った。動画・歌声合成まで含むパイプラインでは
OOM回避を優先するという設計条件に沿い、この時間差を受け入れる。
