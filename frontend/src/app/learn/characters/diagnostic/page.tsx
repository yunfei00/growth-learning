"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import { playCorrectFeedback, playIncorrectFeedback } from "@/lib/child-feedback-audio";
import {
  createLiteracyDiagnosticAudioAttempt,
  createLiteracyDiagnosticSpeechAttempt,
  getLiteracyDiagnosticOverview,
  startLiteracyDiagnostic,
  submitLiteracyDiagnosticItems,
  type LiteracyDiagnosticOutcome,
  type LiteracyDiagnosticOverview,
  type LiteracyDiagnosticSession,
  type LiteracyDiagnosticTarget,
} from "@/lib/literacy-diagnostic-api";
import { nextDiagnosticTarget } from "@/lib/literacy-diagnostic";
import type {
  SpeechRecognitionErrorCode,
  SpeechRecognitionProvider,
} from "@/lib/speech-recognition";
import { createBrowserSpeechRecognitionProvider } from "@/lib/speech-recognition";
import {
  createShortAudioRecorder,
  type ShortAudioRecorder,
} from "@/lib/short-audio-recorder";

import styles from "./page.module.css";

function formatDate(value: string | null): string {
  if (!value) return "暂无";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(new Date(value));
}

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function errorCodeFrom(reason: unknown): string {
  if (typeof reason === "object" && reason && "code" in reason) {
    return String((reason as { code?: unknown }).code ?? "unknown");
  }
  if (reason instanceof Error) return reason.message;
  return "unknown";
}

function DiagnosticContent() {
  const { activeChild, children, setActiveChildId, status } = useActiveChild();
  const [overview, setOverview] = useState<LiteracyDiagnosticOverview | null>(null);
  const [session, setSession] = useState<LiteracyDiagnosticSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [speechStarted, setSpeechStarted] = useState(false);
  const [manualMode, setManualMode] = useState(false);
  const [listening, setListening] = useState(false);
  const [breakDue, setBreakDue] = useState(false);
  const browserProviderRef = useRef<SpeechRecognitionProvider | null>(null);
  const recorderRef = useRef<ShortAudioRecorder | null>(null);
  const serverAsrUnavailableRef = useRef(false);
  const questionStartedAt = useRef(0);
  const submittingRef = useRef(false);
  const autoListenTargetRef = useRef<string | null>(null);
  const childId = activeChild?.id ?? "";

  const loadOverview = useCallback(async () => {
    if (!childId) return;
    setLoading(true);
    try {
      const value = await getLiteracyDiagnosticOverview(childId);
      setOverview(value);
      serverAsrUnavailableRef.current = false;
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "识字检测信息加载失败"));
    } finally {
      setLoading(false);
    }
  }, [childId]);

  useEffect(() => {
    browserProviderRef.current ??= createBrowserSpeechRecognitionProvider();
    recorderRef.current ??= createShortAudioRecorder();
    return () => {
      browserProviderRef.current?.abort();
      recorderRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!childId) return;
    const timer = window.setTimeout(() => {
      browserProviderRef.current?.abort();
      recorderRef.current?.abort();
      serverAsrUnavailableRef.current = false;
      autoListenTargetRef.current = null;
      questionStartedAt.current = 0;
      setSession(null);
      setSpeechStarted(false);
      setManualMode(false);
      setBreakDue(false);
      setFeedback("");
      void loadOverview();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [childId, loadOverview]);

  const currentTarget = session ? nextDiagnosticTarget(session.targets) : null;
  const currentTargetId = currentTarget?.knowledge_point_id ?? null;

  const applyAttemptToSession = useCallback(
    (
      targetId: string,
      attempt: Awaited<ReturnType<typeof createLiteracyDiagnosticSpeechAttempt>>,
    ) => {
      setSession((value) =>
        value
          ? {
              ...value,
              targets: value.targets.map((target) =>
                target.knowledge_point_id === targetId
                  ? {
                      ...target,
                      speech_attempts: [
                        ...target.speech_attempts.filter((item) => item.id !== attempt.id),
                        attempt,
                      ],
                    }
                  : target,
              ),
            }
          : value,
      );
    },
    [],
  );

  const submitOutcome = useCallback(
    async (
      target: LiteracyDiagnosticTarget,
      outcome: LiteracyDiagnosticOutcome,
      evaluationMethod: "parent_manual" | "speech_assisted",
      speechAttemptIds: string[] = [],
    ) => {
      if (!childId || !session || submittingRef.current) return;
      submittingRef.current = true;
      try {
        const updated = await submitLiteracyDiagnosticItems(childId, session.id, [
          {
            knowledge_point_id: target.knowledge_point_id,
            outcome,
            response_time_ms: Math.max(
              0,
              Math.round(performance.now() - questionStartedAt.current),
            ),
            evaluation_method: evaluationMethod,
            speech_attempt_ids: speechAttemptIds,
          },
        ]);
        setSession(updated);
        setBreakDue(updated.segment_break_due);
        if (updated.status === "completed") {
          setSpeechStarted(false);
          await loadOverview();
        } else if (!updated.segment_break_due) {
          questionStartedAt.current = performance.now();
          autoListenTargetRef.current = null;
          setFeedback("");
        }
      } catch (requestError) {
        setError(messageFrom(requestError, "检测结果保存失败，请稍后重试"));
      } finally {
        submittingRef.current = false;
      }
    },
    [childId, loadOverview, session],
  );

  const handleSavedAttempt = useCallback(
    async (
      target: LiteracyDiagnosticTarget,
      saved: Awaited<ReturnType<typeof createLiteracyDiagnosticSpeechAttempt>>,
    ) => {
      applyAttemptToSession(target.knowledge_point_id, saved);
      const attemptIds = [...target.speech_attempts.map((item) => item.id), saved.id];
      if (saved.decision === "match") {
        setFeedback("听到了，很棒！");
        await playCorrectFeedback();
        await submitOutcome(target, "correct", "speech_assisted", attemptIds);
      } else if (saved.decision === "no_match") {
        setFeedback(
          saved.explicit_unknown
            ? "知道啦，我们把这个字留给以后学习。"
            : "读音不对，这个字先记为不认识。",
        );
        await playIncorrectFeedback();
        await submitOutcome(target, "incorrect", "speech_assisted", attemptIds);
      } else {
        setFeedback("这次听到了，但不能可靠确认，先记作待确认。");
        await submitOutcome(target, "uncertain", "speech_assisted", attemptIds);
      }
    },
    [applyAttemptToSession, submitOutcome],
  );

  const listenWithServerAsr = useCallback(
    async (target: LiteracyDiagnosticTarget, attemptIndex: number) => {
      if (!session) return false;
      const recorder = recorderRef.current ?? createShortAudioRecorder();
      recorderRef.current = recorder;
      if (!recorder.supported) return false;
      setFeedback("🎙️ 正在听…读一个字就可以");
      try {
        const recording = await recorder.record({ durationMs: 2600 });
        setFeedback("✨ 正在识别…");
        const saved = await createLiteracyDiagnosticAudioAttempt(childId, session.id, {
          knowledge_point_id: target.knowledge_point_id,
          attempt_index: attemptIndex,
          audio: recording.blob,
          capture_duration_ms: recording.durationMs,
        });
        await handleSavedAttempt(target, saved);
        return true;
      } catch (reason) {
        const code = errorCodeFrom(reason);
        if (code === "not_allowed") {
          setManualMode(true);
          setFeedback("麦克风权限没有开启。请允许麦克风，或由家长判断。");
          return true;
        }
        if (code === "asr_no_speech" || code === "no_speech") {
          setFeedback("没有听到清楚的声音，可以再读一次。技术问题不会算成不认识。");
          return true;
        }
        if (
          code === "server_asr_disabled" ||
          code === "server_asr_configuration_error" ||
          code === "server_asr_transport_error" ||
          code === "server_asr_provider_error"
        ) {
          serverAsrUnavailableRef.current = true;
          setFeedback("高精度语音暂时不可用。再读一次会改用本机识别，也可以家长判断。");
          return true;
        }
        setFeedback("这段录音没有识别成功，可以再读一次。技术问题不会算成不认识。");
        return true;
      }
    },
    [childId, handleSavedAttempt, session],
  );

  const listenWithBrowser = useCallback(
    async (target: LiteracyDiagnosticTarget, attemptIndex: number) => {
      if (!session) return;
      const provider =
        browserProviderRef.current ?? createBrowserSpeechRecognitionProvider();
      browserProviderRef.current = provider;
      if (!provider.supported) {
        setManualMode(true);
        setFeedback(
          provider.unavailableReason === "insecure_context"
            ? "当前地址不是安全连接，请使用 HTTPS；也可以由家长判断。"
            : "当前浏览器暂时不能自动听读，请由家长判断。",
        );
        return;
      }
      const startedAt = performance.now();
      setFeedback("🎙️ 正在用本机识别…");
      try {
        const result = await provider.start({ lang: "zh-CN", timeoutMs: 7000 });
        const saved = await createLiteracyDiagnosticSpeechAttempt(childId, session.id, {
          knowledge_point_id: target.knowledge_point_id,
          attempt_index: attemptIndex,
          provider: result.provider,
          transcript: result.transcript,
          alternatives: result.alternatives,
          confidence: result.confidence,
          confidence_available: result.confidence_available,
          duration_ms: Math.round(performance.now() - startedAt),
          decision: "uncertain",
          provider_metadata: { language: result.language, fallback: true },
        });
        await handleSavedAttempt(target, saved);
      } catch (reason) {
        const code: SpeechRecognitionErrorCode =
          typeof reason === "object" && reason && "code" in reason
            ? (reason as { code: SpeechRecognitionErrorCode }).code
            : "unknown";
        if (code === "not_allowed") {
          setManualMode(true);
          setFeedback("麦克风权限没有开启。请在浏览器中允许麦克风，或由家长判断。");
          return;
        }
        const decision = code === "no_speech" ? "no_speech" : "recognition_error";
        try {
          const saved = await createLiteracyDiagnosticSpeechAttempt(childId, session.id, {
            knowledge_point_id: target.knowledge_point_id,
            attempt_index: attemptIndex,
            provider: "browser_speech_recognition",
            duration_ms: Math.round(performance.now() - startedAt),
            decision,
            provider_metadata: { error_code: code, fallback: true },
          });
          applyAttemptToSession(target.knowledge_point_id, saved);
        } catch {
          // A transport diagnostic must never become a child knowledge outcome.
        }
        if (attemptIndex >= 3) {
          setManualMode(true);
          setFeedback("连续几次没有录清楚，请由家长判断。技术问题不会算成不认识。");
        } else {
          setFeedback(
            code === "no_speech"
              ? "没有听到声音，可以再读一次。"
              : "本机语音也暂时没听清，可以重试或让家长判断。",
          );
        }
      }
    },
    [applyAttemptToSession, childId, handleSavedAttempt, session],
  );

  const listen = useCallback(async () => {
    if (
      !currentTarget ||
      !session ||
      listening ||
      manualMode ||
      breakDue ||
      submittingRef.current
    ) {
      return;
    }
    const attemptIndex = currentTarget.speech_attempts.length + 1;
    if (attemptIndex > 3) {
      setManualMode(true);
      setFeedback("自动听读连续没有判断清楚，请由家长确认这个字。");
      return;
    }
    setListening(true);
    try {
      const shouldUseServer = Boolean(
        overview?.server_asr_enabled && !serverAsrUnavailableRef.current,
      );
      if (shouldUseServer) {
        const handled = await listenWithServerAsr(currentTarget, attemptIndex);
        if (handled) return;
      }
      await listenWithBrowser(currentTarget, attemptIndex);
    } finally {
      setListening(false);
    }
  }, [
    breakDue,
    currentTarget,
    listenWithBrowser,
    listenWithServerAsr,
    listening,
    manualMode,
    overview?.server_asr_enabled,
    session,
  ]);

  useEffect(() => {
    if (!speechStarted || manualMode || breakDue || !currentTargetId || listening) return;
    if (autoListenTargetRef.current === currentTargetId) return;
    autoListenTargetRef.current = currentTargetId;
    const timer = window.setTimeout(() => void listen(), 420);
    return () => window.clearTimeout(timer);
  }, [breakDue, currentTargetId, listen, listening, manualMode, speechStarted]);

  const startOrResume = async () => {
    if (!childId) return;
    setLoading(true);
    setError("");
    setFeedback("");
    try {
      const value = await startLiteracyDiagnostic(childId);
      autoListenTargetRef.current = null;
      questionStartedAt.current = performance.now();
      setSession(value);
      setBreakDue(value.segment_break_due);
      setSpeechStarted(false);
      setManualMode(false);
    } catch (requestError) {
      setError(messageFrom(requestError, "暂时无法开始识字检测"));
    } finally {
      setLoading(false);
    }
  };

  const enableSpeech = () => {
    const recorder = recorderRef.current ?? createShortAudioRecorder();
    const browser =
      browserProviderRef.current ?? createBrowserSpeechRecognitionProvider();
    recorderRef.current = recorder;
    browserProviderRef.current = browser;
    const serverUsable = Boolean(
      overview?.server_asr_enabled && !serverAsrUnavailableRef.current && recorder.supported,
    );
    if (!serverUsable && !browser.supported) {
      setManualMode(true);
      setFeedback(
        recorder.unavailableReason === "insecure_context" ||
          browser.unavailableReason === "insecure_context"
          ? "当前地址需要 HTTPS 才能使用麦克风，已切换家长判断。"
          : "当前浏览器暂时不支持自动听读，已切换家长判断。",
      );
      return;
    }
    autoListenTargetRef.current = null;
    setSpeechStarted(true);
    setManualMode(false);
    setFeedback(
      serverUsable
        ? "准备好了。会使用高精度语音识别，请直接读出屏幕上的大字。"
        : "准备好了，请直接读出屏幕上的大字。",
    );
  };

  const explicitUnknown = async () => {
    if (!currentTarget || !session || submittingRef.current) return;
    browserProviderRef.current?.abort();
    recorderRef.current?.abort();
    const attemptIndex = currentTarget.speech_attempts.length + 1;
    if (attemptIndex <= 3) {
      try {
        const saved = await createLiteracyDiagnosticSpeechAttempt(childId, session.id, {
          knowledge_point_id: currentTarget.knowledge_point_id,
          attempt_index: attemptIndex,
          provider: "child_explicit_unknown",
          transcript: "不知道",
          decision: "no_match",
          explicit_unknown: true,
        });
        applyAttemptToSession(currentTarget.knowledge_point_id, saved);
        setFeedback("知道啦，我们把这个字留给以后学习。");
        await playIncorrectFeedback();
        await submitOutcome(
          currentTarget,
          "incorrect",
          "speech_assisted",
          [...currentTarget.speech_attempts.map((item) => item.id), saved.id],
        );
        return;
      } catch (requestError) {
        setError(messageFrom(requestError, "结果保存失败，请稍后重试"));
        return;
      }
    }
    await submitOutcome(currentTarget, "incorrect", "parent_manual");
  };

  const resumePersistedSession = (value: LiteracyDiagnosticSession) => {
    autoListenTargetRef.current = null;
    questionStartedAt.current = performance.now();
    setFeedback("");
    setSession(value);
    setBreakDue(value.segment_break_due);
  };

  const continueAfterBreak = () => {
    autoListenTargetRef.current = null;
    questionStartedAt.current = performance.now();
    setFeedback("");
    setBreakDue(false);
  };

  if (status === "idle" || status === "loading") {
    return (
      <main className={`${styles.page} section-shell`}>
        <div className={styles.center}>正在准备识字检测…</div>
      </main>
    );
  }
  if (!activeChild) return null;

  if (session) {
    const result = session.result;
    if (session.status === "completed" && result) {
      return (
        <main className={`${styles.page} section-shell`}>
          <header className={styles.header}>
            <div>
              <p className="eyebrow">识字检测完成</p>
              <h1>{activeChild.nickname || activeChild.display_name}的识字情况</h1>
            </div>
            <ChildSwitcher
              activeChildId={activeChild.id}
              childOptions={children}
              onChange={setActiveChildId}
            />
          </header>
          <section className={styles.resultHero}>
            <span>当前 {result.catalog_size} 字库内估算独立识字量</span>
            <strong>约 {result.estimated_known} 字</strong>
            <p>
              95% 估算范围约 {result.lower_bound}～{result.upper_bound} 字
            </p>
          </section>
          <section className={styles.metricGrid}>
            <article><span>本次直接检测</span><strong>{result.sample_size}</strong></article>
            <article><span>独立认识</span><strong>{result.directly_known}</strong></article>
            <article><span>待确认</span><strong>{result.uncertain}</strong></article>
            <article><span>不认识</span><strong>{result.unknown}</strong></article>
            <article><span>未直接检测</span><strong>{result.untested}</strong></article>
          </section>
          <p className={styles.limitation}>{result.limitation}</p>
          <div className={styles.footerActions}>
            <button
              className="button button-secondary"
              onClick={() => {
                setSession(null);
                void loadOverview();
              }}
              type="button"
            >
              返回检测中心
            </button>
            <Link className="button button-primary" href="/learn/characters">
              回到识字学习
            </Link>
          </div>
        </main>
      );
    }

    if (breakDue) {
      return (
        <main className={`${styles.page} section-shell`}>
          <section className={styles.breakCard}>
            <span aria-hidden="true">🌱</span>
            <h1>完成一小段啦！</h1>
            <strong>{session.completed_items} / {session.total_items}</strong>
            <p>
              标准检测分成 {session.total_segments} 小段，每段 {session.segment_size} 个字。
              休息一下不会丢进度。
            </p>
            <div className={styles.footerActions}>
              <button className="button button-primary" onClick={continueAfterBreak} type="button">
                继续下一段
              </button>
              <Link className="button button-secondary" href="/learn/characters">
                今天先到这里
              </Link>
            </div>
          </section>
        </main>
      );
    }

    return (
      <main className={`${styles.page} section-shell`}>
        <header className={styles.testHeader}>
          <div>
            <p className="eyebrow">标准识字检测</p>
            <h1>{session.completed_items + 1} / {session.total_items}</h1>
          </div>
          <span>第 {session.current_segment} / {session.total_segments} 段</span>
        </header>
        {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
        {currentTarget ? (
          <section className={styles.testCard}>
            <p className={styles.status} aria-live="polite">
              {feedback || (listening ? "🎙️ 正在听…" : manualMode ? "请孩子读完后，由家长判断" : "请直接读出这个字")}
            </p>
            <strong className={styles.glyph}>{currentTarget.character}</strong>
            <p className={styles.rule}>检测时不显示拼音和读音提示；不会的字可以直接点“🤷”。</p>
            {!speechStarted && !manualMode ? (
              <div className={styles.primaryActions}>
                <button className="button button-primary" onClick={enableSpeech} type="button">
                  🎙️ 开启麦克风
                </button>
                <button className="button button-secondary" onClick={() => setManualMode(true)} type="button">
                  家长判断
                </button>
              </div>
            ) : manualMode ? (
              <div className={styles.manualActions}>
                <button disabled={loading} onClick={() => void submitOutcome(currentTarget, "correct", "parent_manual")} type="button">
                  <span>✓</span>认识
                </button>
                <button disabled={loading} onClick={() => void submitOutcome(currentTarget, "uncertain", "parent_manual")} type="button">
                  <span>?</span>不确定
                </button>
                <button disabled={loading} onClick={() => void submitOutcome(currentTarget, "incorrect", "parent_manual")} type="button">
                  <span>🤷</span>不认识
                </button>
                <button className={styles.modeLink} onClick={enableSpeech} type="button">
                  再试自动听读
                </button>
              </div>
            ) : (
              <div className={styles.speechActions}>
                <button disabled={listening} onClick={() => void listen()} type="button">
                  🎙️ 重试录音
                </button>
                <button disabled={listening} onClick={() => void explicitUnknown()} type="button">
                  🤷 不知道
                </button>
                <button
                  disabled={listening}
                  onClick={() => {
                    browserProviderRef.current?.abort();
                    recorderRef.current?.abort();
                    setManualMode(true);
                  }}
                  type="button"
                >
                  家长判断
                </button>
              </div>
            )}
          </section>
        ) : (
          <div className={styles.center}>正在整理检测结果…</div>
        )}
      </main>
    );
  }

  const latest = overview?.latest_result;
  const active = overview?.active_session;
  return (
    <main className={`${styles.page} section-shell`}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">语文 · 识字</p>
          <h1>识字检测</h1>
          <p>用代表性样本了解孩子目前在 1200 字学习路径中的独立识字情况。</p>
        </div>
        <ChildSwitcher activeChildId={activeChild.id} childOptions={children} onChange={setActiveChildId} />
      </header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {loading && !overview ? (
        <div className={styles.center}>正在读取检测记录…</div>
      ) : (
        <>
          {latest ? (
            <section className={styles.latestCard}>
              <div><span>最近一次标准检测</span><small>{formatDate(latest.created_at)}</small></div>
              <strong>约 {latest.estimated_known} / {latest.catalog_size} 字</strong>
              <p>
                95% 估算范围约 {latest.lower_bound}～{latest.upper_bound} 字 · 本次直接认识{" "}
                {latest.directly_known} / {latest.sample_size}
              </p>
            </section>
          ) : null}
          <section className={styles.introCard}>
            <div>
              <p className="eyebrow">推荐方式</p>
              <h2>120 字标准检测</h2>
              <p>
                系统会沿当前 1200 字库均匀取样；生产 1200 字库中每连续 10 字抽 1 字，共
                120 字。题目一旦生成就固定，刷新或隔天继续都不会重抽。
              </p>
            </div>
            <div className={styles.featureList}>
              <span>4 小段 × 30 字</span>
              <span>{overview?.server_asr_enabled ? "高精度云端听读，技术失败可本机/家长判断" : "语音优先，也可家长判断"}</span>
              <span>每个字按第一次有效读音判定，只有技术问题才重试</span>
              <span>没有提示音，不提前暴露答案</span>
              <span>技术没听清 ≠ 孩子不认识</span>
            </div>
            {active ? (
              <button className="button button-primary" disabled={loading} onClick={() => resumePersistedSession(active)} type="button">
                继续检测 · {active.completed_items} / {active.total_items}
              </button>
            ) : (
              <button className="button button-primary" disabled={loading} onClick={() => void startOrResume()} type="button">
                开始标准检测
              </button>
            )}
            <small className={styles.limitation}>{overview?.limitation ?? "未直接检测的汉字不会被自动判定。"}</small>
          </section>
          <section className={styles.explainGrid}>
            <article>
              <strong>估算 ≠ 全量确认</strong>
              <p>120 字用于估算整体水平；只有真正测过的字才会留下“认识 / 待确认 / 不认识”的直接证据。</p>
            </article>
            <article>
              <strong>检测 ≠ 学习</strong>
              <p>检测不会创建识字学习记录。一次读对也不会直接变成“稳定掌握”，仍由长期证据决定。</p>
            </article>
          </section>
          {overview?.history.length ? (
            <section className={styles.history}>
              <h2>检测历史</h2>
              {overview.history.map((item) => (
                <article key={item.id}>
                  <div>
                    <strong>{formatDate(item.completed_at ?? item.started_at)}</strong>
                    <span>{item.status === "completed" ? "已完成" : `进行中 ${item.completed_items}/${item.total_items}`}</span>
                  </div>
                  {item.result ? (
                    <p>约 {item.result.estimated_known} 字 · 直接认识 {item.directly_known} · 待确认 {item.uncertain} · 不认识 {item.unknown}</p>
                  ) : (
                    <p>已完成 {item.completed_items} / {item.total_items}</p>
                  )}
                </article>
              ))}
            </section>
          ) : null}
          <div className={styles.footerActions}>
            <Link className="button button-secondary" href="/learn/characters">返回识字学习</Link>
          </div>
        </>
      )}
    </main>
  );
}

export default function LiteracyDiagnosticPage() {
  return (
    <ProtectedPage>
      <DiagnosticContent />
    </ProtectedPage>
  );
}
