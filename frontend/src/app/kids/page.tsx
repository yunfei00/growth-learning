"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ChildToday,
  getChildToday,
  type Subject,
} from "@/lib/api/client";

const TASK_ICONS: Record<string, string> = {
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

function ChildHomeContent() {
  const { status, activeChild, error: householdError, refresh } = useActiveChild();
  const [today, setToday] = useState<ChildToday | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setToday(await getChildToday(activeChild.id));
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "小树暂时休息了，请再试一次",
      );
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status === "idle" || status === "loading") {
    return (
      <section className="child-state" aria-live="polite">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在看看今天有什么好玩的…</p>
      </section>
    );
  }
  if (status === "error" || !activeChild) {
    return (
      <section className="child-state" aria-live="polite">
        <div aria-hidden="true" className="child-state-icon">🌤️</div>
        <h1>暂时没有找到孩子档案</h1>
        <p>{householdError || "请回到家长模式选择一个孩子"}</p>
        <button className="child-primary-action" onClick={() => void refresh()} type="button">
          重新试试
        </button>
      </section>
    );
  }

  const childName = activeChild.nickname || activeChild.display_name;
  return (
    <section className="child-page child-home-page">
      <header className="child-welcome">
        <div>
          <p>今天也会长出新叶子</p>
          <h1>你好，{childName} 👋</h1>
        </div>
        <div className="child-star-pill" aria-label={`当前有 ${today?.star_balance ?? 0} 颗星`}>
          ⭐ {today?.star_balance ?? 0}
        </div>
      </header>

      {error ? (
        <div className="child-error" role="alert">
          <span aria-hidden="true">🌦️</span>
          <div><strong>暂时没有加载成功</strong><p>{error}</p></div>
          <button onClick={() => void load()} type="button">重新尝试</button>
        </div>
      ) : null}

      <section className="child-today-card">
        <div className="child-section-heading">
          <div><span>☀️</span><h2>今天要做</h2></div>
          <Link href="/kids/today">查看全部</Link>
        </div>
        {!today ? (
          <div className="child-loading-cards" aria-label="正在加载今日任务">
            <span /><span /><span />
          </div>
        ) : today.tasks.length === 0 ? (
          <div className="child-empty">
            <span aria-hidden="true">🎈</span>
            <strong>今天的任务都完成啦</strong>
            <p>可以去读故事，或者和爸爸妈妈一起做个实验。</p>
          </div>
        ) : (
          <div className="child-task-list">
            {today.tasks.slice(0, 4).map((task) => (
              <Link
                className={`child-task-row status-${task.status}`}
                href={task.href}
                key={`${task.kind}-${task.source_id ?? task.title}`}
              >
                <span className="child-task-icon" aria-hidden="true">
                  {TASK_ICONS[task.kind]}
                </span>
                <span className="child-task-copy">
                  <strong>{task.title}</strong>
                  <small>{SUBJECT_LABELS[task.subject]} · {task.description}</small>
                </span>
                <span className="child-task-cta">
                  {task.status === "completed" ? "完成啦 ✓" : task.cta_label}
                </span>
              </Link>
            ))}
          </div>
        )}
        {today?.continue_task ? (
          <Link className="child-resume-banner" href={today.continue_task.href}>
            <span aria-hidden="true">▶</span>
            <span><strong>继续上次的任务</strong><small>{today.continue_task.title}</small></span>
          </Link>
        ) : null}
      </section>

      <nav aria-label="孩子模式功能" className="child-feature-grid">
        <Link href="/kids/stories"><span aria-hidden="true">📖</span><strong>我的故事</strong><small>去故事里旅行</small></Link>
        <Link href="/kids/science"><span aria-hidden="true">🔬</span><strong>科学实验</strong><small>发现小秘密</small></Link>
        <Link href="/kids/growth-tree"><span aria-hidden="true">🌳</span><strong>成长树</strong><small>看看新叶子</small></Link>
        <Link href="/kids/achievements"><span aria-hidden="true">🏅</span><strong>我的成就</strong><small>收藏成长时刻</small></Link>
      </nav>
    </section>
  );
}

export default function ChildHomePage() {
  return <ProtectedPage><ChildHomeContent /></ProtectedPage>;
}
