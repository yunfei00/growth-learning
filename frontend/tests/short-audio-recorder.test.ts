import assert from "node:assert/strict";
import test from "node:test";

import { resolveShortAudioRecorderAvailability } from "../src/lib/short-audio-recorder.ts";

test("short audio recording requires a secure browser context", () => {
  assert.deepEqual(
    resolveShortAudioRecorderAvailability({
      secureContext: false,
      hasMediaDevices: true,
      hasMediaRecorder: true,
    }),
    { supported: false, unavailableReason: "insecure_context" },
  );
});

test("short audio recording requires both getUserMedia and MediaRecorder", () => {
  assert.deepEqual(
    resolveShortAudioRecorderAvailability({
      secureContext: true,
      hasMediaDevices: false,
      hasMediaRecorder: true,
    }),
    { supported: false, unavailableReason: "not_supported" },
  );
  assert.deepEqual(
    resolveShortAudioRecorderAvailability({
      secureContext: true,
      hasMediaDevices: true,
      hasMediaRecorder: false,
    }),
    { supported: false, unavailableReason: "not_supported" },
  );
});

test("short audio recording is available when all browser primitives exist", () => {
  assert.deepEqual(
    resolveShortAudioRecorderAvailability({
      secureContext: true,
      hasMediaDevices: true,
      hasMediaRecorder: true,
    }),
    { supported: true, unavailableReason: null },
  );
});
