import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  MATH_DIRECT_PRAISES,
  MATH_HINTED_PRAISES,
  mathPraise,
  mathRetryHint,
} from "../src/lib/math-child-feedback.ts";

const detail = readFileSync(
  new URL("../src/app/learn/math/[knowledgePointId]/page.tsx", import.meta.url),
  "utf8",
);

test("math praise rotates through multiple confidence-building messages", () => {
  assert.ok(MATH_DIRECT_PRAISES.length >= 6);
  assert.ok(MATH_HINTED_PRAISES.length >= 4);
  assert.notEqual(mathPraise(false, 0), mathPraise(false, 1));
  assert.notEqual(mathPraise(true, 0), mathPraise(true, 1));
  assert.equal(mathPraise(false, MATH_DIRECT_PRAISES.length), MATH_DIRECT_PRAISES[0]);
  assert.equal(mathPraise(true, MATH_HINTED_PRAISES.length), MATH_HINTED_PRAISES[0]);
});

test("quantity retry hints are actionable and do not reveal the answer", () => {
  const hints = Array.from({ length: 4 }, (_, index) => mathRetryHint("quantity", index));
  assert.equal(new Set(hints).size, 4);
  assert.ok(hints.some((hint) => hint.includes("一个一个")));
  assert.ok(hints.some((hint) => hint.includes("点着数")));
  assert.ok(hints.every((hint) => !/正确答案/.test(hint)));
});

test("child practice keeps an incorrect problem open, then praises a solved retry", () => {
  assert.match(detail, /session\.mode === "practice" && result\.outcome === "incorrect"/);
  assert.match(detail, /setHintUsed\(true\)/);
  assert.match(detail, /setAnswered\(false\)/);
  assert.match(detail, /setCorrectAnswer\(undefined\)/);
  assert.match(detail, /answerLocked\.current = false/);
  assert.match(detail, /const solved = result\.outcome !== "incorrect"/);
  assert.match(detail, /const praise = mathPraise\(hintUsed, feedbackTurn\.current\+\+\)/);
  assert.match(detail, /childFeedbackAudio\.speakInstruction\(praise\)/);
  assert.doesNotMatch(detail, /再看看哦。正确答案亮起来了。/);
  assert.doesNotMatch(detail, /Math\.random/);
});
