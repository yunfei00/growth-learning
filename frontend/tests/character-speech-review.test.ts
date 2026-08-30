import assert from "node:assert/strict";
import test from "node:test";

import {
  initialSpeechReviewMachine,
  reduceSpeechReviewMachine,
} from "../src/lib/review-speech-machine.ts";
import { speechPracticeFeedback } from "../src/lib/speech-practice.ts";
import { resolveSpeechRecognitionAvailability } from "../src/lib/speech-recognition.ts";

test("speech review retries silence twice then records uncertain", () => {
  let state = reduceSpeechReviewMachine(initialSpeechReviewMachine, { type: "START" });
  state = reduceSpeechReviewMachine(state, { type: "READY" });
  state = reduceSpeechReviewMachine(state, { type: "LISTEN" });
  state = reduceSpeechReviewMachine(state, { type: "NO_SPEECH" });
  assert.equal(state.state, "retry_prompt");
  state = reduceSpeechReviewMachine(state, { type: "RETRY" });
  state = reduceSpeechReviewMachine(state, { type: "NO_SPEECH" });
  assert.equal(state.state, "retry_prompt");
  state = reduceSpeechReviewMachine(state, { type: "RETRY" });
  state = reduceSpeechReviewMachine(state, { type: "NO_SPEECH" });
  assert.equal(state.state, "feedback_uncertain");
  assert.equal(state.attemptIndex, 2);
});

test("hint is persistent state and a successful read remains hinted_correct", () => {
  let state = reduceSpeechReviewMachine(initialSpeechReviewMachine, { type: "HINT" });
  assert.equal(state.hintUsed, true);
  state = reduceSpeechReviewMachine(state, { type: "CORRECT" });
  assert.equal(state.state, "feedback_correct");
  assert.equal(state.hintUsed, true);
});

test("explicit unknown is a negative outcome while ordinary ASR mismatch is retryable", () => {
  const unknown = reduceSpeechReviewMachine(initialSpeechReviewMachine, { type: "UNKNOWN" });
  assert.equal(unknown.state, "feedback_incorrect");
  const mismatch = reduceSpeechReviewMachine(initialSpeechReviewMachine, {
    type: "RESULT",
    decision: "no_match",
  });
  assert.equal(mismatch.state, "retry_prompt");
});

test("speech review exposes a distinct recognition state", () => {
  const listening = reduceSpeechReviewMachine(initialSpeechReviewMachine, { type: "LISTEN" });
  const recognizing = reduceSpeechReviewMachine(listening, { type: "RECOGNIZE" });
  assert.equal(recognizing.state, "recognizing");
});

test("free speech practice gives feedback without defining an assessment outcome", () => {
  assert.deepEqual(speechPracticeFeedback("match"), {
    kind: "correct",
    message: "读对啦！",
  });
  assert.equal(speechPracticeFeedback("no_match").kind, "uncertain");
  assert.equal(speechPracticeFeedback("no_speech").kind, "uncertain");
});

test("insecure origins are reported accurately even when Chrome hides the speech API", () => {
  assert.deepEqual(
    resolveSpeechRecognitionAvailability({ secureContext: false, hasRecognitionApi: false }),
    { supported: false, unavailableReason: "insecure_context" },
  );
  assert.deepEqual(
    resolveSpeechRecognitionAvailability({ secureContext: true, hasRecognitionApi: false }),
    { supported: false, unavailableReason: "not_supported" },
  );
  assert.deepEqual(
    resolveSpeechRecognitionAvailability({ secureContext: true, hasRecognitionApi: true }),
    { supported: true, unavailableReason: null },
  );
});
