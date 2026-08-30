import type { SpeechReviewDecision } from "@/lib/api/client";

export function speechPracticeFeedback(decision: SpeechReviewDecision): {
  kind: "correct" | "uncertain";
  message: string;
} {
  if (decision === "match") return { kind: "correct", message: "读对啦！" };
  if (decision === "no_speech" || decision === "recognition_error") {
    return { kind: "uncertain", message: "我没有听清，再说一次吧。" };
  }
  return { kind: "uncertain", message: "这个读音还不确定，再试一次吧。" };
}

