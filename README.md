# soramimic

空耳(替え歌)歌詞を自動生成する [Soramimic](https://soramimic.com) エンジンの Python ライブラリです。
本体( soramimic/soramimic の `frontend/src/lib` )の**挙動互換移植**で、同じ入力・同じ単語リストから本体と同じ空耳を生成します。

> 開発中(0.x)。API は変わる可能性があります。

## インストール

```bash
pip install soramimic          # コア(トークナイザなし)
pip install "soramimic[mecab]" # fugashi + ipadic トークナイザ込み
```

## 使い方

```python
from soramimic import create_soramimic, load_default_data
from soramimic.tokenizers.mecab import MeCabTokenizer  # 要 soramimic[mecab]

tok = MeCabTokenizer()
app = create_soramimic(
    **load_default_data(),  # 同梱の辞書データ(漢字読み・英語カナ・音類似度など)
    tokenize_sentenses=tok.tokenize,
    get_yomi=tok.get_yomi,
)

# 単語リスト: tidy CSV (soramimic-wordlists 形式) または1行1語のプレーンテキスト。
# 試しやすいようにサンプル(nations=国名, sekitsui=脊椎動物, stations=駅名)を同梱している
from soramimic import load_sample_wordlist

db = app.word_list.parse_tidy(load_sample_wordlist("nations"), "")  # 第2引数はwhere式

results = app.soramimi_maker.generate(["夜の街を駆け抜ける"], db, {})
for line in results:
    print(" / ".join(w["surface"] for w in line))
# => ヨルダン / マリ / オマーン / ペルー / ペルー
```

自前の単語リストを使う場合は同形式のCSVテキストを `parse_tidy` に渡します。
同梱サンプルは権利上の配慮から事実データ(国名・生物名・駅名)のみです。

トークナイザは差し替え可能です( `soramimic.tokenizer.Tokenizer` プロトコル参照)。
kuromoji.js 互換のトークン dict( `surface_form` / `pronunciation` / `pos` …、未知語は `"*"` )を返せば何でも使えます。
事前にトークナイズ済みの入力からは `generate_from_tokens()` で生成できます(固定区間 `locks` による部分再生成にも対応)。

### soramimic.com 現行版と同じ設定で生成する

本体フロントエンドは monophone タイブレーク行列(#102)と新パラメータ
( `MID_PHRASE_BREAK_PENALTY` #98 / `VARIATION_COST` #105 )を使います。
同じ経路は次のように組みます( `r` は「音の合わせ方」= vowelRatio、既定 0.8 ):

```python
from soramimic import create_soramimic, load_default_data, scale_similarity

r = 0.8
data = load_default_data(similarity="monotie")
app = create_soramimic(
    **{**data,
       "vowel_similarity": scale_similarity(data["vowel_similarity"], 2 * r),
       "consonant_similarity": scale_similarity(data["consonant_similarity"], 2 * (1 - r))},
    tokenize_sentenses=tok.tokenize,
    get_yomi=tok.get_yomi,
)
# 本体「バランス」プリセット相当のパラメータ
param = {"SAME_PHRASE_BREAK_REWARD": 0, "MID_PHRASE_BREAK_PENALTY": 20,
         "WORD_NUMBER_PENALTY": 20, "VARIATION_COST": 20 * r}
```

### ユニット位置別の重み付けで合わせる音を優先する

`generate` / `generate_from_tokens` の省略可能な `weights_per_line` に、行ごとの
「音節ユニット位置別の重み」(非負float、長さはその行の音節ユニット数)を渡すと、
その位置の音の一致を重く見て単語を選びます。長い音符の音を優先して合わせたい、
といった用途向けです。**省略時(None)は従来と完全に同一の動作**です。

```python
# 1行目の先頭2ユニット(=長い音符)を重く、残りは軽く
results = app.soramimi_maker.generate_from_tokens(
    tokens_list, db, param, weights_per_line=[[3, 3, 1, 1, 1]]
)
```

重みは行ごとに**平均1へ正規化**されます(`w_i * n / sum(w)`)。単語数ペナルティや
文節境界の報酬/ペナルティのような「位置を持たない定数項」との相対スケールを保つ
ためで、重みの絶対値ではなく行内の相対的な強弱だけが効きます。長さ不一致や
合計0以下・負値などの不正な重みは warning ログを出してその行を重みなし扱いにします。

現時点で重みが掛かるのは音の一致距離のみで、`VARIATION_COST` ・
`WORD_NUMBER_PENALTY` ・文節境界項は無重みのままです。

### 歌詞にルビ記法で読みを指定する(`｜表層《よみ》`)

歌詞に青空文庫ルビ記法を書くと、その区間の読みを形態素解析の推定より優先できます。
辞書に無い当て字・固有名詞(`｜邪悪《ダークネス》`)で効きます。

```python
results = app.soramimi_maker.generate(["｜邪悪《ダークネス》を飼い慣らせ"], db, param)
```

- 開始記号は `｜`(U+FF5C)と `|`(U+007C)の両方、読み括弧は `《》` のみ。
- `\｜` `\|` `\《` `\》` `\\` はエスケープ(文字そのもの)。
- `《よみ》` が続かない `｜`、`｜` を伴わない `《…》`、表層や読みが空の記法、
  改行をまたぐ記法は、いずれも通常の文字として扱います(暗黙形ルビは未対応)。
- **記法を含まない入力の出力は従来と完全に同一**です。

パーサ単体も公開しています(素テキストと区間注釈への分解のみ)。

```python
from soramimic import parse_ruby

parse_ruby("｜邪悪《ダークネス》を飼い慣らせ")
# => {"plain": "邪悪を飼い慣らせ",
#     "annotations": [{"start": 0, "end": 2, "reading": "ダークネス"}]}
```

`start` / `end` は `plain` 上のコードポイントオフセット(`end` は排他)です。

### 大きな単語リストの前処理を速くする(`max_units`)

単語リストの前処理( `parse_tidy` / `parse_plain` )は、各単語の読みからン・ッ・母音連続
の揺れを展開した**発音バリエーション**を全通り作ります。この数は音節数に対して指数的に
増える(該当する音節1つにつき2〜5通りに分岐する)ため、極端に長い読みが1語混じるだけで
前処理が何分もかかることがあります。`format_kana` が本体JS由来のバグで「英字を複数語含む
表層」の読みを繰り返してしまうので、英名入りの単語リストでは実際に起こります。

バリエーションは**ユニット数が完全一致するターゲットとしか照合されない**
( `maker._ld` は長さ不一致を Infinity にする)ので、生成対象の歌詞行の最大ユニット数を
超えるバリエーションは作っても使われません。`max_units` を渡すとその上限で直積を
枝刈りします。

```python
db = app.word_list.parse_tidy(csv_text, "", max_units=40)
```

結果は `{k: v for k, v in parse_tidy(csv_text, "").items() if k <= max_units}` と完全に
同一です(順序・ `vcost` ・ `src` 込み)。**省略時(None)は従来と完全に同一の動作**なので、
上限を歌詞行の最大ユニット数以上にしておけば生成結果は変わりません。

## 本体JSとの互換性

- モジュールは本体 `frontend/src/lib` の各JSファイルと1:1対応です( `kanaToSyllable.js` → `kana_to_syllable.py` など)。
- 互換性は**ゴールデンテスト**で担保しています。`tools/generate_golden.mjs` が本体JSを Node で直接実行して期待出力( `tests/golden/*.json` )を生成し、pytest で Python 出力との完全一致を検証します。本体更新への追従時は次で再生成してください:

```bash
node tools/generate_golden.mjs <soramimicリポジトリのルート> tests/golden
uv run pytest tests/test_golden.py
```

- JS実装の癖(オブジェクトのキー列挙順、共有ミューテーション、既知の細かなバグを含む)も出力互換のため忠実に再現しています。詳細は各モジュールのコメント参照。

## 開発

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
```

## License

MIT。同梱の英語発音データ( `english-kana.json` )は CMUdict 由来です( `src/soramimic/data/english-kana.LICENSE` 参照)。
