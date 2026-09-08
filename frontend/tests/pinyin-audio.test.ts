import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { resolvePinyinPlayback } from "../src/lib/pinyin-playback.ts";

const targetAudio = (
  displayText: string,
  speechText: string | null,
  mode: "curated" | "tts_fallback" | "missing" = "tts_fallback",
  kind?: "initial" | "final" | "tone" | "whole",
) => ({
  display_text: displayText,
  kind,
  audio: {
    mode,
    audio_url: mode === "curated" ? "/api/v1/pinyin/items/point/audio" : null,
    speech_text: speechText,
    purpose: "target_pronunciation" as const,
    target_pronunciation: displayText,
  },
});

test("Pinyin fallback accepts only a short verified target proxy", () => {
  assert.deepEqual(resolvePinyinPlayback(targetAudio("b", "玻")), {
    mode: "tts_fallback",
    speechText: "玻",
  });

  for (const [symbol, unsafe] of [
    ["b", "b"],
    ["p", "p"],
    ["m", "m"],
    ["f", "f"],
    ["d", "d"],
    ["t", "t"],
    ["b", "玻，玻璃的玻。"],
    ["à", "第四声，大树的大，声音干脆下降。"],
  ] as const) {
    assert.deepEqual(resolvePinyinPlayback(targetAudio(symbol, unsafe)), { mode: "missing" });
  }
});

test("all four tones reject teaching explanations and example words", () => {
  const cases = [
    ["ā", ["阿姨", "第一声", "声音平平"]],
    ["á", ["回答", "答", "第二声"]],
    ["ǎ", ["小马", "马", "第三声"]],
    ["à", ["大树", "大", "第四声"]],
  ] as const;

  for (const [tone, forbidden] of cases) {
    for (const text of forbidden) {
      assert.deepEqual(resolvePinyinPlayback(targetAudio(tone, text, "tts_fallback", "tone")), {
        mode: "missing",
      });
    }
  }
});

test("curated Pinyin target audio keeps the authenticated API base path", () => {
  assert.deepEqual(resolvePinyinPlayback(targetAudio("a", null, "curated"), "/growth/api"), {
    mode: "curated",
    url: "/growth/api/api/v1/pinyin/items/point/audio",
  });
});

test("main, replay, follow-along, and listening assessment share target playback", () => {
  const detailPage = readFileSync(
    new URL("../src/app/learn/pinyin/[knowledgePointId]/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(detailPage, /const played = await playPinyinAudio\(item\)/);
  assert.match(detailPage, /const played = await play\(\);[\s\S]*setListeningOpen\(true\)/);
  assert.doesNotMatch(detailPage, /speakChinese\(item\.pronunciation_cue\)/);
  assert.match(detailPage, /只听目标音/);

  const blendingPage = readFileSync(
    new URL("../src/app/learn/pinyin/blending/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(blendingPage, /playPinyinAudio\(practice\)/);
  assert.doesNotMatch(blendingPage, /speakChinese\(practice\.pronunciation_cue\)/);
});
