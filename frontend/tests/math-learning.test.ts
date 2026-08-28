import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const overview = readFileSync(new URL("../src/app/learn/math/page.tsx", import.meta.url), "utf8");
const detail = readFileSync(
  new URL("../src/app/learn/math/[knowledgePointId]/page.tsx", import.meta.url),
  "utf8",
);
const today = readFileSync(new URL("../src/app/kids/today/page.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

test("math overview exposes domains, full skill path, and child switching", () => {
  assert.match(overview, /数学成长/);
  assert.match(overview, /DOMAIN_ORDER/);
  assert.match(overview, /math-skill-grid/);
  assert.match(overview, /ChildSwitcher/);
  assert.match(overview, /setActiveChildId/);
});

test("math learning keeps exactly one primary problem on screen", () => {
  assert.match(detail, /math-problem-screen/);
  assert.match(detail, /第 \{index \+ 1\} \/ \{session\?\.problems\.length\} 题/);
  assert.match(detail, /MathProblemVisual/);
  assert.doesNotMatch(detail, /Math\.random/);
});

test("answer interaction persists through backend and preserves hint state", () => {
  assert.match(detail, /answerMathAttempt/);
  assert.match(detail, /submittedAnswer: value/);
  assert.match(detail, /hintUsed/);
  assert.match(detail, /performance\.now\(\)/);
});

test("offline activity observations are evidence-backed and parent-only", () => {
  assert.match(detail, /recordMathOfflineObservation/);
  assert.match(detail, /独立完成/);
  assert.match(detail, /需要提示/);
  assert.match(detail, /暂时不会/);
  assert.match(detail, /!childMode/);
  assert.match(overview, /item\.mode === "offline" \? "动手活动"/);
});

test("Chinese listening and child-friendly feedback are available", () => {
  assert.match(detail, /SpeechSynthesisUtterance/);
  assert.match(detail, /utterance\.lang = "zh-CN"/);
  assert.match(detail, /🔊 再听一次/);
});

test("Today understands the independent math task kind", () => {
  assert.match(today, /math: "数"/);
  assert.match(today, /SUBJECT_LABELS\[task\.subject\]/);
  assert.match(today, /task\.status === "completed" \? "再看看"/);
});

test("math controls remain large and responsive at phone width", () => {
  assert.match(styles, /\.math-answer-grid button[\s\S]*min-height: 88px/);
  assert.match(styles, /@media \(max-width: 600px\)[\s\S]*\.math-answer-grid/);
  assert.match(styles, /grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/);
});
