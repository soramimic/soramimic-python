# soramimic

空耳(替え歌)歌詞を自動生成する [Soramimic](https://soramimic.com) エンジンの Python ライブラリです。
本体( soramimic/soramimic の `frontend/src/lib` )と挙動互換の移植です。

> 開発中(0.x)。API は変わる可能性があります。

## インストール

```bash
pip install soramimic          # コア(トークナイザなし)
pip install "soramimic[mecab]" # fugashi + ipadic トークナイザ込み
```

## 使い方

準備中。

## License

MIT。同梱の英語発音データ( `english-kana.json` )は CMUdict 由来です( `src/soramimic/data/english-kana.LICENSE` 参照)。
