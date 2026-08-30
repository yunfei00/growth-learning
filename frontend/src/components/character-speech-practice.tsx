"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiClientError,
  evaluateCharacterSpeechPractice,
} from "@/lib/api/client";
import { playCorrectFeedback } from "@/lib/child-feedback-audio";
import {
  createBrowserSpeechRecognitionProvider,
  type SpeechRecognitionErrorCode,
  type SpeechRecognitionProvider,
} from "@/lib/speech-recognition";
import { speechPracticeFeedback } from "@/lib/speech-practice";

type PracticeState =
  | "idle"
  | "listening"
  | "evaluating"
  | "feedback"
  | "unsupported"
  | "error";

type Props = {
  childId: string;
  knowledgePointId: string;
  character: string;
  onClose: () => void;
};

function recognitionErrorMessage(code: SpeechRecognitionErrorCode): string {
  if (code === "not_allowed") return "麦克风没有获得授权，请检查浏览器权限后再试。";
  if (code === "insecure_context") {
    return "当前页面使用 HTTP，浏览器无法稳定开放麦克风。请改用 HTTPS。";
  }
  if (code === "network") return "语音识别服务暂时无法连接，请稍后再试。";
  return "我没有听清，再说一次吧。";
}

export function CharacterSpeechPractice({
  childId,
  knowledgePointId,
  character,
  onClose,
}: Props) {
  const providerRef = useRef<SpeechRecognitionProvider | null>(null);
  const [state, setState] = useState<PracticeState>("idle");
  const [message, setMessage] = useState("这次只是口头练习，不会修改复习结果。");

  useEffect(() => {
    providerRef.current = createBrowserSpeechRecognitionProvider();
    return () => providerRef.current?.abort();
  }, []);

  const start = async () => {
    const provider = providerRef.current ?? createBrowserSpeechRecognitionProvider();
    providerRef.current = provider;
    if (!provider.supported) {
      setState("unsupported");
      setMessage(recognitionErrorMessage(provider.unavailableReason ?? "not_supported"));
      return;
    }

    setState("listening");
    setMessage("🎙️ 正在听…");
    try {
      // start() stays inside the user gesture so the browser can show its permission prompt.
      const recognition = await provider.start({ timeoutMs: 5000 });
      setState("evaluating");
      setMessage("正在听你读…");
      const result = await evaluateCharacterSpeechPractice(childId, knowledgePointId, {
        transcript: recognition.transcript,
        alternatives: recognition.alternatives,
        confidence: recognition.confidence,
        confidence_available: recognition.confidence_available,
      });
      const feedback = speechPracticeFeedback(result.decision);
      setState("feedback");
      setMessage(feedback.message);
      if (feedback.kind === "correct") await playCorrectFeedback();
    } catch (reason) {
      const code = typeof reason === "object" && reason && "code" in reason
        ? (reason as { code: SpeechRecognitionErrorCode }).code
        : null;
      setState("error");
      setMessage(
        code
          ? recognitionErrorMessage(code)
          : reason instanceof ApiClientError
            ? reason.message
            : "口头练习暂时不可用，请稍后再试。",
      );
    }
  };

  const active = state === "listening" || state === "evaluating";
  return (
    <aside className="character-speech-practice" aria-label="口头练一练">
      <div className="speech-practice-topline">
        <strong>🎙️ 口头练一练</strong>
        <button disabled={active} onClick={onClose} type="button">关闭</button>
      </div>
      <strong className="speech-practice-glyph">{character}</strong>
      <p aria-live="polite" className={`speech-practice-message ${state}`}>{message}</p>
      <button
        className="button button-primary"
        disabled={active}
        onClick={() => void start()}
        type="button"
      >
        {state === "idle" ? "开启麦克风" : active ? "正在听…" : "再读一次"}
      </button>
      <small>自由练习不会创建 AssessmentItem，不会修改掌握度或今日完成数。</small>
    </aside>
  );
}

