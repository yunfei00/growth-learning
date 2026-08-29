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
const visual = readFileSync(
  new URL("../src/components/math-problem-visual.tsx", import.meta.url),
  "utf8",
);
const feedbackAudio = readFileSync(
  new URL("../src/lib/child-feedback-audio.ts", import.meta.url),
  "utf8",
);

test("math overview exposes domains, full skill path, and child switching", () => {
  assert.match(overview, /数学成长/);
  assert.match(overview, /DOMAIN_ORDER/);
  assert.match(overview, /math-skill-grid/);
  assert.match(overview, /ChildSwitcher/);
  assert.match(overview, /setActiveChildId/);
});

test("child math opens the first problem and keeps exactly one primary task on screen", () => {
  assert.match(detail, /math-problem-screen/);
  assert.match(detail, /第 \{index \+ 1\} \/ \{session\?\.problems\.length\} 题/);
  assert.match(detail, /MathProblemVisual/);
  assert.match(detail, /resolvedChildMode !== true/);
  assert.match(detail, /void begin\("practice"\)/);
  assert.match(detail, /!problem && !childMode/);
  assert.doesNotMatch(detail, /Math\.random/);
});

test("answer interaction persists through backend and preserves hint state", () => {
  assert.match(detail, /answerMathAttempt/);
  assert.match(detail, /submittedAnswer: value/);
  assert.match(detail, /hintUsed/);
  assert.match(detail, /performance\.now\(\)/);
  assert.match(detail, /answerLocked\.current/);
  assert.match(detail, /setCorrectAnswer\(result\.correct_answer\)/);
});

test("offline activity observations are evidence-backed and parent-only", () => {
  assert.match(detail, /recordMathOfflineObservation/);
  assert.match(detail, /独立完成/);
  assert.match(detail, /需要提示/);
  assert.match(detail, /暂时不会/);
  assert.match(detail, /!childMode/);
  assert.match(overview, /item\.mode === "offline" \? "动手活动"/);
});

test("feedback audio is queued before automatic navigation and next-question speech", () => {
  assert.match(feedbackAudio, /class ChildFeedbackAudio/);
  assert.match(feedbackAudio, /playCorrectFeedback/);
  assert.match(feedbackAudio, /playIncorrectFeedback/);
  assert.match(feedbackAudio, /playCompletedFeedback/);
  assert.match(feedbackAudio, /utterance\.lang = "zh-CN"/);
  assert.match(detail, /await playCorrectFeedback\(\)/);
  assert.match(detail, /await playIncorrectFeedback\(\)/);
  assert.match(detail, /await playCompletedFeedback\(\)/);
  assert.match(detail, /moveToProblem\(index \+ 1, session\)/);
  assert.match(detail, /router\.replace/);
  assert.match(detail, /🔊 再听一次/);
});

test("compare, spatial, shape, classification and measurement answers use their visuals", () => {
  assert.match(visual, /usesDirectVisualAnswers/);
  assert.match(visual, /math-compare-side/);
  assert.match(visual, /math-compare-divider/);
  assert.match(visual, /math-spatial-object/);
  assert.match(visual, /math-measurement-object/);
  assert.match(visual, /MathVisualToken/);
  assert.match(visual, /token\.color/);
  assert.match(visual, /visual\.prompt_token/);
  assert.match(visual, /math-classification-prompt/);
  assert.match(detail, /!directVisualAnswer/);
  assert.match(detail, /!childMode \? <small>\{option\.label\}<\/small> : null/);
});

test("zero has an explicit empty container instead of a blank visual", () => {
  assert.match(visual, /math-empty-container/);
  assert.match(visual, /空盘子，一个也没有/);
  assert.match(visual, /visual\.empty_meaning === true/);
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
  assert.match(styles, /height: calc\(100dvh - 144px\)/);
  assert.match(styles, /math-problem-feedback:not\(\.has-message\)/);
  assert.match(styles, /math-compare-divider/);
});
