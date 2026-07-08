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

# 単語リスト: tidy CSV (soramimic-wordlists 形式) または1行1語のプレーンテキスト
csv = """id,original,surface,pronunciation
1,ヨーグルト,ヨーグルト,ヨーグルト
2,ケーキ,ケーキ,ケーキ
3,カケル,カケル,カケル
4,ヨル,ヨル,ヨル
5,マチ,マチ,マチ
6,オー,オー,オー
"""
db = app.word_list.parse_tidy(csv, "")  # 第2引数はwhere式 (例: "category = food")

results = app.soramimi_maker.generate(["夜の街を駆け抜ける"], db, {})
for line in results:
    print(" / ".join(w["surface"] for w in line))
# => ヨル / オー / マチ / オー / カケル / ケーキ
```

トークナイザは差し替え可能です( `soramimic.tokenizer.Tokenizer` プロトコル参照)。
kuromoji.js 互換のトークン dict( `surface_form` / `pronunciation` / `pos` …、未知語は `"*"` )を返せば何でも使えます。
事前にトークナイズ済みの入力からは `generate_from_tokens()` で生成できます(固定区間 `locks` による部分再生成にも対応)。

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
