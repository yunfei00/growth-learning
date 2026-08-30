"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  createCharacterSpeechAttempt,
  markPlannedAssessmentHint,
  type AssessmentTarget,
  type PlannedAssessment,
  type SpeechAttempt,
  type SpeechReviewDecision,
} from "@/lib/api/client";
import { childFeedbackAudio, playCorrectFeedback, playIncorrectFeedback } from "@/lib/child-feedback-audio";
import {
  createBrowserSpeechRecognitionProvider,
  type SpeechRecognitionErrorCode,
  type SpeechRecognitionProvider,
} from "@/lib/speech-recognition";
import {
  initialSpeechReviewMachine,
  reduceSpeechReviewMachine,
  type SpeechReviewMachine,
} from "@/lib/review-speech-machine";
import { speakChinese } from "@/lib/speech";

const DECISION_LABELS: Record<SpeechReviewDecision, string> = {
  match: "听到了，很棒！",
  partial_match: "再慢一点试试。",
  uncertain: "我们再听一遍。",
  no_match: "再试一次就好。",
  no_speech: "没有听清，再说一次。",
  recognition_error: "没有听清，再说一次。",
};

type Props = {
  childId: string;
  session: PlannedAssessment;
  target: AssessmentTarget;
  disabled?: boolean;
  onOutcome: (outcome: "correct" | "hinted_correct" | "uncertain" | "incorrect", attemptIds: string[]) => Promise<void>;
  onSessionUpdate: (session: PlannedAssessment) => void;
  onFallback: () => void;
};

export function CharacterSpeechReview({
  childId,
  session,
  target,
  disabled = false,
  onOutcome,
  onSessionUpdate,
  onFallback,
}: Props) {
  const providerRef = useRef<SpeechRecognitionProvider | null>(null);
  const targetInitializedRef = useRef<string | null>(null);
  const [started, setStarted] = useState(false);
  const [machine, setMachine] = useState<SpeechReviewMachine>(initialSpeechReviewMachine);
  const [attempts, setAttempts] = useState<SpeechAttempt[]>([]);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);

  const dispatch = useCallback((event: Parameters<typeof reduceSpeechReviewMachine>[1]) => {
    setMachine((value) => reduceSpeechReviewMachine(value, event));
  }, []);

  useEffect(() => {
    providerRef.current ??= createBrowserSpeechRecognitionProvider();
    return () => {
      providerRef.current?.abort();
      childFeedbackAudio.cancel();
    };
  }, []);

  useEffect(() => {
    if (targetInitializedRef.current === target.knowledge_point_id) return;
    targetInitializedRef.current = target.knowledge_point_id;
    const timer = window.setTimeout(() => {
      setAttempts(target.speech_attempts ?? []);
      setMachine({ ...initialSpeechReviewMachine, hintUsed: Boolean(target.hint_requested_at) });
      setFeedback("");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [target.knowledge_point_id, target.speech_attempts, target.hint_requested_at]);

  const saveAttempt = useCallback(async (
    payload: Parameters<typeof createCharacterSpeechAttempt>[2],
  ) => {
    const result = await createCharacterSpeechAttempt(childId, session.id, payload);
    setAttempts((items) => [...items.filter((item) => item.id !== result.id), result]);
    return result;
  }, [childId, session.id]);

  const handleRecognitionError = useCallback(async (code: SpeechRecognitionErrorCode) => {
    const decision: SpeechReviewDecision = code === "no_speech" ? "no_speech" : "recognition_error";
    const result = await saveAttempt({
      knowledge_point_id: target.knowledge_point_id,
      attempt_index: machine.attemptIndex + 1,
      provider: "browser_speech_recognition",
      decision,
      hint_used: machine.hintUsed,
      provider_metadata: { error_code: code },
    });
    dispatch(code === "no_speech" ? { type: "NO_SPEECH" } : { type: "ERROR" });
    if (machine.attemptIndex >= 2) {
      setFeedback("没关系，我们先记作不确定。还可以继续学习。");
      await onOutcome("uncertain", [...attempts.map((item) => item.id), result.id]);
    } else {
      setFeedback("没有听清，再说一次吧。");
    }
  }, [attempts, dispatch, machine.attemptIndex, machine.hintUsed, onOutcome, saveAttempt, target.knowledge_point_id]);

  const listen = useCallback(async () => {
    const provider = providerRef.current ?? createBrowserSpeechRecognitionProvider();
    providerRef.current = provider;
    if (!provider.supported) {
      dispatch({ type: "UNSUPPORTED" });
      return;
    }
    dispatch({ type: "LISTEN" });
    setFeedback("");
    const startedAt = performance.now();
    try {
      const result = await provider.start({ timeoutMs: 5000 });
      const saved = await saveAttempt({
        knowledge_point_id: target.knowledge_point_id,
        attempt_index: machine.attemptIndex + 1,
        provider: result.provider,
        transcript: result.transcript,
        alternatives: result.alternatives,
        confidence: result.confidence,
        confidence_available: result.confidence_available,
        duration_ms: Math.round(performance.now() - startedAt),
        decision: "uncertain",
        hint_used: machine.hintUsed,
        provider_metadata: { language: result.language },
      });
      const decision = saved.decision;
      if (decision === "match") {
        dispatch({ type: "RESULT", decision: "match" });
        setFeedback(DECISION_LABELS[decision]);
        await playCorrectFeedback();
        await onOutcome(machine.hintUsed ? "hinted_correct" : "correct", [...attempts.map((item) => item.id), saved.id]);
      } else if (machine.attemptIndex >= 2) {
        setFeedback("没关系，我们先记作不确定。还可以继续学习。");
        await onOutcome("uncertain", [...attempts.map((item) => item.id), saved.id]);
      } else {
        setFeedback(DECISION_LABELS[decision]);
        dispatch({
          type: "RESULT",
          decision: decision === "partial_match" || decision === "uncertain" || decision === "no_match"
            ? decision
            : "uncertain",
        });
      }
    } catch (reason) {
      const code = typeof reason === "object" && reason && "code" in reason
        ? (reason as { code: SpeechRecognitionErrorCode }).code
        : "unknown";
      await handleRecognitionError(code);
    }
  }, [attempts, dispatch, handleRecognitionError, machine.attemptIndex, machine.hintUsed, onOutcome, saveAttempt, target.knowledge_point_id]);

  useEffect(() => {
    if (!started || machine.state === "retry_prompt" || machine.state === "advancing") return;
    if (machine.state !== "ready" && machine.state !== "idle") return;
    const timer = window.setTimeout(() => void listen(), 420);
    return () => window.clearTimeout(timer);
  }, [listen, machine.state, started, target.knowledge_point_id]);

  const start = () => {
    dispatch({ type: "START" });
    const provider = providerRef.current ?? createBrowserSpeechRecognitionProvider();
    providerRef.current = provider;
    if (!provider.supported) {
      dispatch({ type: "UNSUPPORTED" });
      return;
    }
    setStarted(true);
    dispatch({ type: "READY" });
  };

  const retry = () => {
    dispatch({ type: "RETRY" });
    void listen();
  };

  const requestHint = async () => {
    if (busy) return;
    setBusy(true);
    dispatch({ type: "HINT" });
    try {
      providerRef.current?.abort();
      speakChinese(target.character);
      const updated = await markPlannedAssessmentHint(childId, session.id, target.knowledge_point_id);
      onSessionUpdate(updated);
      setFeedback("跟着读一遍吧");
      window.setTimeout(() => {
        dispatch({ type: "RETRY" });
        void listen();
      }, 1300);
    } finally {
      setBusy(false);
    }
  };

  const explicitUnknown = async () => {
    if (busy) return;
    setBusy(true);
    providerRef.current?.abort();
    try {
      const saved = await saveAttempt({
        knowledge_point_id: target.knowledge_point_id,
        attempt_index: machine.attemptIndex + 1,
        provider: "child_explicit_unknown",
        transcript: "不知道",
        decision: "no_match",
        explicit_unknown: true,
        hint_used: machine.hintUsed,
      });
      dispatch({ type: "UNKNOWN" });
      setFeedback("我们一起再看一遍这个字。");
      await playIncorrectFeedback();
      await onOutcome("incorrect", [...attempts.map((item) => item.id), saved.id]);
    } finally {
      setBusy(false);
    }
  };

  if (machine.state === "unsupported") {
    return <div className="speech-review-fallback"><h3>这个设备暂时不能自动听读音</h3><p>可以继续使用普通复习模式，掌握度不会被设备能力影响。</p><button className="button button-secondary" onClick={onFallback} type="button">使用普通复习模式</button></div>;
  }
  if (!started) {
    return <div className="speech-review-consent"><span aria-hidden="true">🎙️</span><h3>今天我来听你读字 😊</h3><p>点击后只会把短暂的识别文字用于本次复习，不保存录音。</p><button className="button button-primary" disabled={disabled} onClick={start} type="button">开启麦克风</button></div>;
  }
  const listening = machine.state === "listening" || machine.state === "recognizing";
  return (
    <div className="speech-review-card">
      <div className="speech-review-status" aria-live="polite">{listening ? "正在听…" : feedback || "请读出这个字"}</div>
      <strong className="speech-review-glyph">{target.character}</strong>
      <p className="speech-review-privacy">拼音和答案先隐藏，读完后会给你温柔提示。</p>
      <div className="speech-review-actions">
        <button aria-label="播放提示" className="speech-hint-button" disabled={busy || listening} onClick={() => void requestHint()} type="button">🔊 提示</button>
        <button className="speech-retry-button" disabled={busy || listening} onClick={retry} type="button">再读一次</button>
        <button className="speech-unknown-button" disabled={busy || listening} onClick={() => void explicitUnknown()} type="button">我不知道</button>
      </div>
      {machine.state === "retry_prompt" ? <p className="speech-review-retry">再试一次吧（最多两次重试）</p> : null}
    </div>
  );
}
