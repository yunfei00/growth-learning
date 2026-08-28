import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const overview = readFileSync(new URL("../src/app/learn/english/page.tsx", import.meta.url), "utf8");
const detail = readFileSync(
  new URL("../src/app/learn/english/[knowledgePointId]/page.tsx", import.meta.url),
  "utf8",
);
const playback = readFileSync(new URL("../src/lib/english-playback.ts", import.meta.url), "utf8");
const today = readFileSync(new URL("../src/app/kids/today/page.tsx", import.meta.url), "utf8");
const hub = readFileSync(new URL("../src/app/learn/page.tsx", import.meta.url), "utf8");
const admin = readFileSync(new URL("../src/app/admin/english/page.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

test("English is an independent learning entry with four content paths", () => {
  assert.match(hub, /href="\/learn\/english"/);
  assert.match(overview, /KIND_ORDER.*word.*letter.*phonics.*phrase/);
  assert.match(overview, /英语声音乐园/);
  assert.match(overview, /EnglishVisualCard/);
});

test("one primary English question is rendered with sound replay separate from hints", () => {
  assert.match(detail, /english-problem-screen/);
  assert.match(detail, /第 \{index \+ 1\} \/ \{session\?\.problems\.length\} 题/);
  assert.match(detail, /audioReplays/);
  assert.match(detail, /给我中文提示/);
  assert.match(detail, /setHintUsed\(true\)/);
  assert.match(detail, /再听一次/);
});

test("English playback fixes an en-US voice without using browser language defaults", () => {
  assert.match(playback, /utterance\.lang = audio\.accent \|\| "en-US"/);
  assert.match(playback, /utterance\.rate = 0\.72/);
  assert.match(playback, /audio\.audio_url/);
});

test("speaking is a parent observation and independent assessment remains distinct", () => {
  assert.match(detail, /recordEnglishSpeakingObservation/);
  assert.match(detail, /不使用自动语音评分/);
  assert.match(detail, /begin\("assessment", value\.dimension\)/);
  assert.match(detail, /!childMode/);
});

test("Today and admin understand English as a first-class subject", () => {
  assert.match(today, /english: "🔊"/);
  assert.match(admin, /同步 english-foundation-v1/);
  assert.match(admin, /Phonics 缺少正式音素/);
  assert.match(admin, /audioStatus/);
  assert.match(admin, /visualStatus/);
});

test("English controls and cards remain child-sized on phones", () => {
  assert.match(styles, /\.english-answer-grid > button,[\s\S]*min-height: 150px/);
  assert.match(styles, /@media \(max-width: 600px\)[\s\S]*\.english-answer-grid/);
  assert.match(styles, /grid-template-columns: 1fr/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});
