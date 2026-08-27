import assert from "node:assert/strict";
import test from "node:test";

import { resolvePinyinPlayback } from "../src/lib/pinyin-playback.ts";

test("Pinyin fallback speaks a Chinese cue instead of an English letter name", () => {
  assert.deepEqual(
    resolvePinyinPlayback({
      display_text: "b",
      audio: { mode: "tts_fallback", audio_url: null, speech_text: "玻，玻璃的玻。" },
    }),
    { mode: "tts_fallback", speechText: "玻，玻璃的玻。" },
  );
  assert.deepEqual(
    resolvePinyinPlayback({
      display_text: "b",
      audio: { mode: "tts_fallback", audio_url: null, speech_text: "b" },
    }),
    { mode: "missing" },
  );
});

test("curated Pinyin audio keeps the authenticated API base path", () => {
  assert.deepEqual(
    resolvePinyinPlayback(
      {
        display_text: "a",
        audio: {
          mode: "curated",
          audio_url: "/api/v1/pinyin/items/point/audio",
          speech_text: null,
        },
      },
      "/growth/api",
    ),
    { mode: "curated", url: "/growth/api/api/v1/pinyin/items/point/audio" },
  );
});
