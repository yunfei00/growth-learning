import assert from "node:assert/strict";
import test from "node:test";

import {
  diagnosticCounts,
  diagnosticSegmentNumber,
  nextDiagnosticTarget,
  shouldOfferDiagnosticBreak,
} from "../src/lib/literacy-diagnostic.ts";

test("standard diagnostic offers rests after each completed 30-character segment", () => {
  assert.equal(shouldOfferDiagnosticBreak(0, 120), false);
  assert.equal(shouldOfferDiagnosticBreak(29, 120), false);
  assert.equal(shouldOfferDiagnosticBreak(30, 120), true);
  assert.equal(shouldOfferDiagnosticBreak(60, 120), true);
  assert.equal(shouldOfferDiagnosticBreak(90, 120), true);
  assert.equal(shouldOfferDiagnosticBreak(120, 120), false);
  assert.equal(diagnosticSegmentNumber(0, 120), 1);
  assert.equal(diagnosticSegmentNumber(30, 120), 2);
  assert.equal(diagnosticSegmentNumber(90, 120), 4);
  assert.equal(diagnosticSegmentNumber(120, 120), 4);
});

test("diagnostic counts only direct outcomes and leaves untested items untouched", () => {
  const targets = [
    { outcome: "correct" as const },
    { outcome: "uncertain" as const },
    { outcome: "incorrect" as const },
    { outcome: null },
  ];
  assert.deepEqual(diagnosticCounts(targets), {
    correct: 1,
    uncertain: 1,
    incorrect: 1,
    completed: 3,
  });
  assert.equal(nextDiagnosticTarget(targets), targets[3]);
});
