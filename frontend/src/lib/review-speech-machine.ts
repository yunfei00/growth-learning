export type SpeechReviewState =
  | "idle"
  | "requesting_permission"
  | "ready"
  | "listening"
  | "recognizing"
  | "retry_prompt"
  | "playing_hint"
  | "feedback_correct"
  | "feedback_uncertain"
  | "feedback_incorrect"
  | "advancing"
  | "completed"
  | "unsupported"
  | "error";

export type SpeechReviewMachine = { state: SpeechReviewState; attemptIndex: number; hintUsed: boolean };

export type SpeechReviewEvent =
  | { type: "START" }
  | { type: "READY" }
  | { type: "LISTEN" }
  | { type: "RESULT"; decision: "match" | "partial_match" | "uncertain" | "no_match" }
  | { type: "NO_SPEECH" }
  | { type: "ERROR" }
  | { type: "RETRY" }
  | { type: "HINT" }
  | { type: "CORRECT" }
  | { type: "UNKNOWN" }
  | { type: "NEXT" }
  | { type: "COMPLETE" }
  | { type: "UNSUPPORTED" };

export const initialSpeechReviewMachine: SpeechReviewMachine = {
  state: "idle",
  attemptIndex: 0,
  hintUsed: false,
};

export function reduceSpeechReviewMachine(
  machine: SpeechReviewMachine,
  event: SpeechReviewEvent,
): SpeechReviewMachine {
  switch (event.type) {
    case "START": return { ...machine, state: "requesting_permission" };
    case "READY": return { ...machine, state: "ready" };
    case "LISTEN": return { ...machine, state: "listening" };
    case "RESULT":
      if (event.decision === "match") return { ...machine, state: "feedback_correct" };
      return machine.attemptIndex < 2
        ? { ...machine, state: "retry_prompt", attemptIndex: machine.attemptIndex + 1 }
        : { ...machine, state: "feedback_uncertain" };
    case "NO_SPEECH":
    case "ERROR":
      return machine.attemptIndex < 2
        ? { ...machine, state: "retry_prompt", attemptIndex: machine.attemptIndex + 1 }
        : { ...machine, state: "feedback_uncertain" };
    case "RETRY": return { ...machine, state: "listening" };
    case "HINT": return { ...machine, state: "playing_hint", hintUsed: true };
    case "CORRECT": return { ...machine, state: "feedback_correct" };
    case "UNKNOWN": return { ...machine, state: "feedback_incorrect" };
    case "NEXT": return { ...machine, state: "advancing", attemptIndex: 0, hintUsed: false };
    case "COMPLETE": return { ...machine, state: "completed" };
    case "UNSUPPORTED": return { ...machine, state: "unsupported" };
    default: return machine;
  }
}
