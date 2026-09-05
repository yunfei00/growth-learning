"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  getLiteracyDiagnosticSession,
  type LiteracyDiagnosticOutcome,
  type LiteracyDiagnosticSession,
  type LiteracyDiagnosticTarget,
} from "@/lib/literacy-diagnostic-api";

import styles from "./page.module.css";

type DetailFilter = "all" | LiteracyDiagnosticOutcome;

const FILTERS: Array<{ value: DetailFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "correct", label: "认识" },
  { value: "uncertain", label: "待确认" },
  { value: "incorrect", label: "不认识" },
];

const OUTCOME_LABEL: Record<LiteracyDiagnosticOutcome, string> = {
  correct: "认识",
  uncertain: "待确认",
  incorrect: "不认识",
};

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function latestSpeechSummary(target: LiteracyDiagnosticTarget): {
  transcript: string | null;
  readings: string[];
  provider: string | null;
} {
  const attempt = [...target.speech_attempts]
    .sort((a, b) => b.attempt_index - a.attempt_index)
    .find((item) => item.transcript || item.normalized_readings.length > 0);
  return {
    transcript: attempt?.transcript ?? null,
    readings: attempt?.normalized_readings ?? [],
    provider: attempt?.provider ?? null,
  };
}

function ResultDetail() {
  const params = useParams<{ sessionId: string }>();
  const { activeChild, status } = useActiveChild();
  const [session, setSession] = useState<LiteracyDiagnosticSession | null>(null);
  const [filter, setFilter] = useState<DetailFilter>("all");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild?.id || !params.sessionId) return;
    try {
      const value = await getLiteracyDiagnosticSession(activeChild.id, params.sessionId);
      setSession(value);
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "暂时无法读取这次识字检测详情"));
    }
  }, [activeChild?.id, params.sessionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const completed = useMemo(
    () => session?.targets.filter((target) => target.outcome !== null) ?? [],
    [session],
  );
  const counts = useMemo(
    () => ({
      correct: completed.filter((target) => target.outcome === "correct").length,
      uncertain: completed.filter((target) => target.outcome === "uncertain").length,
      incorrect: completed.filter((target) => target.outcome === "incorrect").length,
    }),
    [completed],
  );
  const visible = useMemo(
    () =>
      filter === "all"
        ? completed
        : completed.filter((target) => target.outcome === filter),
    [completed, filter],
  );

  if (status === "idle" || status === "loading" || (!session && !error)) {
    return (
      <main className={`${styles.page} section-shell`}>
        <div className={styles.center}>正在读取检测详情…</div>
      </main>
    );
  }

  if (!activeChild) return null;

  return (
    <main className={`${styles.page} section-shell`}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">识字检测记录</p>
          <h1>{activeChild.nickname || activeChild.display_name}的本次检测详情</h1>
          <p>这里显示真正测过的字以及当时的判断依据；未直接检测的字不会出现在这里。</p>
        </div>
        <Link className="button button-secondary" href="/learn/characters/diagnostic">
          返回识字检测
        </Link>
      </header>

      {error ? <p className="form-message form-error">{error}</p> : null}

      {session ? (
        <>
          {session.result ? (
            <section className={styles.resultHero}>
              <span>基于本次 {session.result.sample_size} 字样本的估算识字量</span>
              <strong>约 {session.result.estimated_known} 字</strong>
              <p>
                95% 估算范围约 {session.result.lower_bound}～{session.result.upper_bound} 字
              </p>
            </section>
          ) : (
            <section className={styles.progressCard}>
              本次检测仍在进行中：已完成 {session.completed_items} / {session.total_items}
            </section>
          )}

          <section className={styles.summaryGrid}>
            <article><span>已检测</span><strong>{completed.length}</strong></article>
            <article><span>认识</span><strong>{counts.correct}</strong></article>
            <article><span>待确认</span><strong>{counts.uncertain}</strong></article>
            <article><span>不认识</span><strong>{counts.incorrect}</strong></article>
          </section>

          <section className={styles.detailCard}>
            <div className={styles.detailHeader}>
              <div>
                <h2>逐字检测结果</h2>
                <p>语音辅助会显示识别到的文字/读音；家长手动判断会明确标记。</p>
              </div>
              <div className={styles.filters} role="group" aria-label="筛选检测结果">
                {FILTERS.map((item) => (
                  <button
                    aria-pressed={filter === item.value}
                    className={filter === item.value ? styles.activeFilter : ""}
                    key={item.value}
                    onClick={() => setFilter(item.value)}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {visible.length ? (
              <div className={styles.resultList}>
                {visible.map((target) => {
                  const outcome = target.outcome as LiteracyDiagnosticOutcome;
                  const speech = latestSpeechSummary(target);
                  return (
                    <article className={styles.resultRow} key={target.knowledge_point_id}>
                      <div className={styles.characterBlock}>
                        <strong>{target.character}</strong>
                        <span>{target.pinyin}</span>
                      </div>
                      <div className={styles.evidenceBlock}>
                        <span className={`${styles.outcome} ${styles[outcome]}`}>
                          {OUTCOME_LABEL[outcome]}
                        </span>
                        <p>
                          判断方式：
                          {target.evaluation_method === "parent_manual" ? "家长判断" : "语音辅助"}
                        </p>
                        {target.evaluation_method === "speech_assisted" ? (
                          <>
                            <p>
                              识别内容：
                              {speech.transcript || speech.readings.join(" / ") || "未留下可用文字"}
                            </p>
                            {speech.transcript && speech.readings.length ? (
                              <p>标准化读音：{speech.readings.join(" / ")}</p>
                            ) : null}
                          </>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className={styles.empty}>这个筛选条件下没有记录。</p>
            )}
          </section>

          <p className={styles.note}>
            识字量是基于代表性样本的统计估算，不代表系统已经逐字确认全部 1200 个汉字。
          </p>
        </>
      ) : null}
    </main>
  );
}

export default function LiteracyDiagnosticResultPage() {
  return (
    <ProtectedPage>
      <ResultDetail />
    </ProtectedPage>
  );
}
