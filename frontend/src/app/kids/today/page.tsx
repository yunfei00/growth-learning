"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { ApiClientError, type ChildToday, getChildToday, type Subject } from "@/lib/api/client";

const ICONS: Record<string, string> = {
  new: "🌱",
  review: "🔁",
  reading: "📖",
  science: "🔬",
  teacher: "🧑‍🏫",
};

const SUBJECT_LABELS: Record<Subject, string> = {
  chinese: "语文",
  math: "数学",
  english: "英语",
  science: "科学",
};

function ChildTodayContent() {
  const { status, activeChild } = useActiveChild();
  const [today, setToday] = useState<ChildToday | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setToday(await getChildToday(activeChild.id));
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "暂时无法打开今天的任务",
      );
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild) {
    return <section className="child-state"><span className="loading-spinner" /><p>正在准备今天的任务…</p></section>;
  }

  return (
    <section className="child-page child-today-page">
      <header className="child-page-title">
        <span aria-hidden="true">☀️</span>
        <div><p>{today?.plan_date ?? "今天"}</p><h1>今天的成长任务</h1></div>
      </header>
      {error ? (
        <div className="child-error" role="alert">
          <span aria-hidden="true">🌦️</span><div><strong>任务暂时躲起来了</strong><p>{error}</p></div>
          <button onClick={() => void load()} type="button">重新尝试</button>
        </div>
      ) : null}
      {!today ? (
        <div className="child-state compact"><span className="loading-spinner" /><p>正在排好今天的顺序…</p></div>
      ) : today.tasks.length === 0 ? (
        <div className="child-empty child-celebration"><span aria-hidden="true">🎉</span><h2>今天都完成啦</h2><p>每一次认真参与，都会让成长树多一片新叶子。</p></div>
      ) : (
        <div className="child-today-stack">
          {today.tasks.map((task, index) => (
            <article className={`child-today-task status-${task.status}`} key={`${task.kind}-${task.source_id ?? index}`}>
              <div className="child-task-number" aria-hidden="true">{task.status === "completed" ? "✓" : index + 1}</div>
              <span className="child-today-icon" aria-hidden="true">{ICONS[task.kind]}</span>
              <div><small>{SUBJECT_LABELS[task.subject]}</small><h2>{task.title}</h2><p>{task.description}</p></div>
              <Link href={task.href}>{task.status === "completed" ? "再看看" : task.cta_label}</Link>
            </article>
          ))}
        </div>
      )}
      <p className="child-kind-note">遇到还不熟悉的内容也没关系，成长就是慢慢发芽。</p>
    </section>
  );
}

export default function ChildTodayPage() {
  return <ProtectedPage><ChildTodayContent /></ProtectedPage>;
}
