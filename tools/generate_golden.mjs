// ゴールデンフィクスチャ生成スクリプト
// soramimic本体(main)のJS libを「正」として実行し、Python移植の期待出力JSONを生成する。
// 読み推定(kuromoji/MeCab)は使わず、事前に用意した固定トークン・固定読みのみを入力に
// することで、トークナイザ差に依存しないアルゴリズム部分の一致を検証できるようにする。
//
// 実行: node generate_golden.mjs <soramimic-main-root> <outdir>
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const [, , ROOT, OUTDIR] = process.argv;
if (!ROOT || !OUTDIR) {
  console.error("usage: node generate_golden.mjs <soramimic-main-root> <outdir>");
  process.exit(1);
}
mkdirSync(OUTDIR, { recursive: true });

const libUrl = (f) => pathToFileURL(join(ROOT, "frontend/src/lib", f)).href;
const { createSoramimic } = await import(libUrl("index.js"));

const loadJson = (f) => JSON.parse(readFileSync(join(ROOT, "data", f), "utf8"));
const kanjiDict = loadJson("kanjiyomi.json");
const englishDict = loadJson("english-kana.json");
const romanTree = loadJson("tree_roma2kana.json");
const vowelSimilarity = loadJson("simVowelsSimple.json");
const consonantSimilarity = loadJson("simConsonantsSimple.json");
const kana2phonon = loadJson("kana2phonon.json");

// console.logノイズを抑制(fixture出力を汚さない)
const origLog = console.log;
console.log = () => {};
console.time = () => {};
console.timeEnd = () => {};
console.timeLog = () => {};

// トークナイザは注入しない前提のケースのみ扱う(getYomiだけ固定辞書のfake)
const fakeYomiTable = {
  "東京": "トーキョー",
  "山手": "ヤマノテ",
  "秋葉原": "アキハバラ",
};
const fakeGetYomi = (text) => {
  const one = (t) => fakeYomiTable[t] ?? t;
  return Array.isArray(text) ? text.map(one) : one(text);
};
const fakeTokenize = () => {
  throw new Error("tokenize should not be called in golden fixtures");
};

const app = createSoramimic({
  kanjiDict,
  englishDict,
  romanTree,
  vowelSimilarity,
  consonantSimilarity,
  kana2phonon,
  tokenizeSentenses: fakeTokenize,
  getYomi: fakeGetYomi,
});

const { textAnalyzer, kanaSimilarity, soramimiMaker, wordList } = app;

// ---------------------------------------------------------------
// 1. kanaToSyllable: split / variation
const kanaInputs = [
  "トーキョー",
  "アイウエオ",
  "シンジュク",
  "キャリーバッグ",
  "ヴァイオリン",
  "ンーッ",
  "サッポロラーメン",
  "コンニチハ",
  "ファンタジー",
  "ウィンドウズ",
];
const k2sFixture = kanaInputs.map((k) => {
  const syllables = textAnalyzer.yomiToSyllable(k);
  const variations = textAnalyzer.yomiToVariation(k);
  return { input: k, syllables, variations };
});
writeFileSync(join(OUTDIR, "kana_to_syllable.json"), JSON.stringify(k2sFixture, null, 1));

// ---------------------------------------------------------------
// 2. formatKana
const formatKanaInputs = ["こんにちは", "ラーメン食べたい".replace(/[^ぁ-ヿ]/g, ""), "love", "ヰヱヲ", "きゃっほー!"];
const formatKanaFixture = formatKanaInputs.map((t) => ({ input: t, output: textAnalyzer.formatKana(t) }));
writeFileSync(join(OUTDIR, "format_kana.json"), JSON.stringify(formatKanaFixture, null, 1));

// ---------------------------------------------------------------
// 3. formatTokensList + getYomiAndPhraseBreak
// kuromoji(ipadic)形式の固定トークン(読み推定済み前提)
const tk = (surface, pos, d1, reading, pron, extra = {}) => ({
  surface_form: surface,
  basic_form: surface,
  reading,
  pronunciation: pron,
  pos,
  pos_detail_1: d1,
  pos_detail_2: "*",
  pos_detail_3: "*",
  conjugated_form: "*",
  conjugated_type: "*",
  ...extra,
});
const rawTokensList = [
  // 夜の街を駆け抜ける (読み固定)
  [
    tk("夜", "名詞", "一般", "ヨル", "ヨル"),
    tk("の", "助詞", "連体化", "ノ", "ノ"),
    tk("街", "名詞", "一般", "マチ", "マチ"),
    tk("を", "助詞", "格助詞", "ヲ", "ヲ"),
    tk("駆け抜ける", "動詞", "自立", "カケヌケル", "カケヌケル"),
  ],
  // 英語混じり: LOVEが未知語(*)→英語辞書で読み補完される経路
  [
    tk("love", "名詞", "固有名詞", "*", "*"),
    tk("を", "助詞", "格助詞", "ヲ", "ヲ"),
    tk("叫ぶ", "動詞", "自立", "サケブ", "サケブ"),
  ],
  // かな未知語(*)→カタカナ化される経路 + 記号 + 長音単独トークン
  [
    tk("ぴえん", "名詞", "一般", "*", "*"),
    tk("ー", "名詞", "一般", "*", "*"),
    tk("!", "記号", "一般", "!", "!"),
    tk("超", "接頭詞", "名詞接続", "チョウ", "チョー"),
    tk("えもい", "形容詞", "自立", "*", "*"),
  ],
  // 数字・小書きかな結合の経路
  [
    tk("1", "名詞", "数", "*", "*"),
    tk("じ", "名詞", "接尾", "ジ", "ジ"),
    tk("に", "助詞", "格助詞", "ニ", "ニ"),
    tk("あ", "感動詞", "*", "ア", "ア"),
    tk("っ", "名詞", "一般", "*", "*"),
  ],
];
// formatTokensListはtokenを破壊的に書き換えるためdeep copyを渡す
const formatted = textAnalyzer.formatTokensList(JSON.parse(JSON.stringify(rawTokensList)));
writeFileSync(
  join(OUTDIR, "format_tokens_list.json"),
  JSON.stringify({ input: rawTokensList, output: formatted }, null, 1)
);

const yomiPhrase = formatted.map((tokens) =>
  textAnalyzer.getYomiAndPhraseBreak(JSON.parse(JSON.stringify(tokens)))
);
writeFileSync(
  join(OUTDIR, "yomi_and_phrase_break.json"),
  JSON.stringify({ input: formatted, output: yomiPhrase }, null, 1)
);

// ---------------------------------------------------------------
// 4. wordList: parsePlain / parseTidy
const plainText = [
  "東京タワー,トーキョータワー # コメント",
  "りんご",
  "シンジュク​",
  "スカイツリー,スカイツリー,スカイツリータワー",
  "",
].join("\n");
const plainDb = wordList.parsePlain(plainText);
writeFileSync(join(OUTDIR, "wordlist_plain.json"), JSON.stringify({ input: plainText, output: plainDb }, null, 1));

// pronunciation列が無いCSV(nations.csv形式): surface代用フォールバックの互換確認
const tidyCsvNoPron = [
  "id,original,surface,status",
  "0,アフガニスタン,アフガニスタン,current",
  "1,ニッポン,ニッポン,current",
  "2,ソビエト,ソビエト,former",
].join("\n");
{
  const db = wordList.parseTidy(tidyCsvNoPron, "status = current");
  writeFileSync(
    join(OUTDIR, "wordlist_tidy_no_pronunciation.json"),
    JSON.stringify({ input: tidyCsvNoPron, where: "status = current", output: db }, null, 1)
  );
}

const tidyCsv = [
  "id,original,surface,pronunciation,category",
  "1,山手線,山手線,ヤマノテセン,station",
  "2,秋葉原,秋葉原,アキハバラ,station",
  "3,カレー,カレー,NA,food",
  "4,ラーメン,ラーメン,ラーメン,food",
  "5,ぎょうざ,ぎょうざ,ギョーザ,food",
  "6,パソコン,パソコン,パソコン,gadget",
].join("\n");
for (const where of ["", "category = food", "category = food or category = gadget", "category != station"]) {
  const db = wordList.parseTidy(tidyCsv, where);
  const name = where === "" ? "all" : where.replace(/[^a-z]+/g, "_");
  writeFileSync(
    join(OUTDIR, `wordlist_tidy_${name}.json`),
    JSON.stringify({ input: tidyCsv, where, output: db }, null, 1)
  );
}

// ---------------------------------------------------------------
// 5. kanaSimilarity: 行列そのものは大きいのでサンプル値を固定
const kanaDist = kanaSimilarity.getKanaSimilarity({ LENGTH: 1 });
const simPairs = [];
const kanaKeys = Object.keys(kanaDist).sort();
for (let i = 0; i < kanaKeys.length; i += 7) {
  const a = kanaKeys[i];
  const inner = Object.keys(kanaDist[a]).sort();
  for (let j = 0; j < inner.length; j += 11) {
    simPairs.push([a, inner[j], kanaDist[a][inner[j]]]);
  }
}
writeFileSync(
  join(OUTDIR, "kana_similarity_samples.json"),
  JSON.stringify({ parameter: { LENGTH: 1 }, samples: simPairs }, null, 1)
);

// ---------------------------------------------------------------
// 6. generateFromTokens / getCandidates
const genWordlistCsv = [
  "id,original,surface,pronunciation",
  "1,ヨーグルト,ヨーグルト,ヨーグルト",
  "2,マーチ,マーチ,マーチ",
  "3,カヌレ,カヌレ,カヌレ",
  "4,ケーキ,ケーキ,ケーキ",
  "5,ノルマ,ノルマ,ノルマ",
  "6,サケ,サケ,サケ",
  "7,ブリ,ブリ,ブリ",
  "8,ラブ,ラブ,ラブ",
  "9,ヲタク,ヲタク,ヲタク",
  "10,カケル,カケル,カケル",
  "11,ヨル,ヨル,ヨル",
  "12,マチ,マチ,マチ",
  "13,オー,オー,オー",
  "14,サビ,サビ,サビ",
  "15,クジラ,クジラ,クジラ",
  "16,テーブル,テーブル,テーブル",
  "17,ラーメンヤ,ラーメン屋,ラーメンヤ",
  "18,ボー,棒,ボー",
  "19,チョーエモイ,超エモい,チョーエモイ",
  "20,イチジク,無花果,イチジク",
  "21,ニアミス,ニアミス,ニアミス",
  "22,アット,アット,アット",
].join("\n");
const genDb = wordList.parseTidy(genWordlistCsv, "");

function runGenerate(tokensList, db, parameter, locksPerLine = null) {
  return new Promise((resolve) => {
    soramimiMaker.generateFromTokens(
      JSON.parse(JSON.stringify(tokensList)),
      db,
      parameter,
      null,
      (results) => resolve(results),
      locksPerLine
    );
  });
}

const genCases = [];
for (const [name, parameter] of [
  ["default", {}],
  ["no_duplicate", { DUPLICATE: false }],
  ["phrase_reward", { SAME_PHRASE_BREAK_REWARD: 3, WORD_NUMBER_PENALTY: 2 }],
  // 新パラメータ(#98 MID_PHRASE_BREAK_PENALTY / #105 VARIATION_COST)。
  // 値は本体フロントエンドの「バランス」プリセット相当(r=0.8時の getParam)
  ["new_params", {
    SAME_PHRASE_BREAK_REWARD: 0, MID_PHRASE_BREAK_PENALTY: 20,
    WORD_NUMBER_PENALTY: 20, VARIATION_COST: 16,
  }],
  ["mid_phrase_break_max", { SAME_PHRASE_BREAK_REWARD: 0, MID_PHRASE_BREAK_PENALTY: 160 }],
]) {
  const results = await runGenerate(formatted, genDb, parameter);
  genCases.push({ name, parameter, tokens_list: formatted, results });
}
writeFileSync(
  join(OUTDIR, "generate_from_tokens.json"),
  JSON.stringify({ wordlist_csv: genWordlistCsv, cases: genCases }, null, 1)
);

// ---------------------------------------------------------------
// 7. MonoTie行列 + vowelRatioスケーリング(appCore.js の appFor 相当)。
// soramimic.com 現行版の生成経路(#102)をアプリ組み立てごと検証する
const vowelSimilarityMonoTie = loadJson("simVowelsMonoTie.json");
const consonantSimilarityMonoTie = loadJson("simConsonantsMonoTie.json");
function scaleMatrix(m, f) {
  const out = {};
  for (const k1 in m) {
    out[k1] = {};
    for (const k2 in m[k1]) out[k1][k2] = m[k1][k2] * f;
  }
  return out;
}
const monoTieCases = [];
for (const [name, r, parameter] of [
  // 本体プリセット「バランス」(r=0.8, 文節1→MID20, 単語長2→WNP20)
  ["balance", 0.8, {
    SAME_PHRASE_BREAK_REWARD: 0, MID_PHRASE_BREAK_PENALTY: 20,
    WORD_NUMBER_PENALTY: 20, VARIATION_COST: 16, VOWEL_RATIO: 0.8,
  }],
  // 本体プリセット「文節重視」(文節8→MID160)+ 子音寄り r=0.3
  ["phrase_focus_r03", 0.3, {
    SAME_PHRASE_BREAK_REWARD: 0, MID_PHRASE_BREAK_PENALTY: 160,
    WORD_NUMBER_PENALTY: 20, VARIATION_COST: 6, VOWEL_RATIO: 0.3,
  }],
]) {
  const appR = createSoramimic({
    kanjiDict, englishDict, romanTree, kana2phonon,
    vowelSimilarity: scaleMatrix(vowelSimilarityMonoTie, 2 * r),
    consonantSimilarity: scaleMatrix(consonantSimilarityMonoTie, 2 * (1 - r)),
    tokenizeSentenses: fakeTokenize,
    getYomi: fakeGetYomi,
  });
  const dbR = appR.wordList.parseTidy(genWordlistCsv, "");
  const results = await new Promise((resolve) => {
    appR.soramimiMaker.generateFromTokens(
      JSON.parse(JSON.stringify(formatted)), dbR, parameter, null, resolve
    );
  });
  monoTieCases.push({ name, vowel_ratio: r, parameter, tokens_list: formatted, results });
}
writeFileSync(
  join(OUTDIR, "generate_from_tokens_monotie.json"),
  JSON.stringify({ wordlist_csv: genWordlistCsv, cases: monoTieCases }, null, 1)
);

// getCandidates: 選択範囲の発音ユニット配列に対する候補
const candTargets = [["ヨ", "ル"], ["カ", "ケ", "ヌ", "ケ", "ル"], ["トー", "キョー"]];
const candFixture = candTargets.map((target) => ({
  target,
  output: soramimiMaker.getCandidates(genDb, target, {}, 5),
}));
writeFileSync(
  join(OUTDIR, "get_candidates.json"),
  JSON.stringify({ wordlist_csv: genWordlistCsv, cases: candFixture }, null, 1)
);

console.log = origLog;
console.log("done:", OUTDIR);
