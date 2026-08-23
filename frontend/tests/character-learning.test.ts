import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCharacterLearningHref,
  parseCharacterLearningContext,
  resolveCharacterReturnAction,
} from "../src/lib/character-navigation.ts";
import { activateChineseSpeech, speakChinese } from "../src/lib/speech.ts";

test("character entries preserve return targets for every supported source", () => {
  const cases = [
    ["today", "/learn/characters?view=new"],
    ["system_path", "/courses/system-course?group=9"],
    ["mastery", "/learn/characters/status/proficient?sort=character&page=2"],
    ["records", "/learn/characters?view=records#learning-session-1"],
  ] as const;

  for (const [source, returnTo] of cases) {
    const href = buildCharacterLearningHref("point-86", {
      source,
      returnTo,
      sequence: source === "records" ? "learning_session" : "system_path",
    });
    const query = new URL(href, "https://example.test").searchParams;
    const parsed = parseCharacterLearningContext(query);
    assert.equal(parsed.source, source);
    assert.deepEqual(resolveCharacterReturnAction(parsed.returnTo, true), {
      kind: "url",
      value: returnTo,
    });
  }
});

test("return resolution uses history then the literacy home as safe fallbacks", () => {
  assert.deepEqual(resolveCharacterReturnAction(undefined, true), { kind: "history" });
  assert.deepEqual(resolveCharacterReturnAction("https://unsafe.test", false), {
    kind: "url",
    value: "/learn/characters",
  });
});

test("speech activation never navigates and speaks exactly once", () => {
  let prevented = 0;
  let stopped = 0;
  let cancelled = 0;
  const spoken: Array<{ lang: string; rate: number }> = [];
  const result = activateChineseSpeech(
    {
      preventDefault: () => prevented++,
      stopPropagation: () => stopped++,
    },
    "东方",
    {
      cancel: () => cancelled++,
      speak: (utterance) => spoken.push(utterance),
    },
    () => ({ lang: "", rate: 1 }),
  );
  assert.equal(result, true);
  assert.equal(prevented, 1);
  assert.equal(stopped, 1);
  assert.equal(cancelled, 1);
  assert.deepEqual(spoken, [{ lang: "zh-CN", rate: 0.75 }]);
});

test("unsupported speech synthesis is a no-op", () => {
  assert.equal(speakChinese("东", null, null), false);
});
