"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  type ReadingSeriesProgress,
  getCurrentReadingSeries,
} from "@/lib/reading-series-api";

const STATUS_LABELS = {
  completed: "✅ 已完成",
  in_progress: "📖 阅读中",
  current: "📖 当前",
  upcoming: "○ 后续内容",
} as const;

function ReadingSeriesBrowser() {
  const { status, children, activeChild, setActiveChildId } = useActiveChild();
  const [series, setSeries] = useState<ReadingSeriesProgress | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setSeries(await getCurrentReadingSeries(activeChild.id));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "暂时无法加载连续故事");
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild || !series) {
    return (
      <section className="center-state section-shell">
        {error ? (
          <p className="form-message form-error">{error}</p>
        ) : (
          <>
            <span className="loading-spinner" aria-hidden="true" />
            <p>正在打开 30 天连续故事…</p>
          </>
        )}
      </section>
    );
  }

  return (
    <section className="reading-hub section-shell">
      <div className="dashboard-toolbar">
        <div>
          <p className="eyebrow">30 天连续故事 · 第一季</p>
          <h1>{series.title}</h1>
          <p className="role-note">
            30 天内容都可以随时展开预览。预览未来故事不会算完成，也不会改变正式阅读顺序。
          </p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={(id) => {
            setSeries(null);
            setActiveChildId(id);
          }}
        />
      </div>

      <div className="reader-topbar">
        <Link href="/read">← 我的故事书</Link>
        <Link href="/read/checkins">📅 阅读打卡</Link>
        <Link href="/kids/today">📖 今日任务</Link>
      </div>

      <section className="story-generator-panel">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">本月进度</p>
            <h2>{series.completed_episodes} / {series.total_episodes} 天</h2>
          </div>
          <strong>{series.progress_percent}%</strong>
        </div>
        <progress
          aria-label="连续故事阅读进度"
          max={series.total_episodes}
          style={{ width: "100%", height: "16px" }}
          value={series.completed_episodes}
        />
        <p className="role-note">
          {series.current_episode_number
            ? `当前正式阅读：第 ${series.current_episode_number} 天 · ${series.current_chapter_title} · ${series.current_episode_title}`
            : "🎉 第一季已经全部读完。"}
        </p>
        {series.current_story_version_id ? (
          <Link className="button button-primary" href={`/read/${series.current_story_version_id}`}>
            继续当前正式阅读
          </Link>
        ) : series.current_episode_number ? (
          <Link className="button button-primary" href="/kids/today">
            从今日任务开始正式阅读
          </Link>
        ) : null}
      </section>

      <section className="story-generator-panel">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">完整目录</p>
            <h2>Day 1 — Day 30</h2>
          </div>
          <span>点击任意一天即可预览全文</span>
        </div>

        <div style={{ display: "grid", gap: "12px", marginTop: "18px" }}>
          {series.episodes.map((episode) => (
            <details
              key={episode.episode_number}
              style={{ border: "1px solid currentColor", borderRadius: "16px", padding: "14px 16px" }}
            >
              <summary style={{ cursor: "pointer" }}>
                <strong>第 {episode.episode_number} 天 · {episode.title}</strong>
                <span style={{ marginLeft: "10px" }}>{STATUS_LABELS[episode.status]}</span>
                <small style={{ display: "block", marginTop: "4px" }}>{episode.chapter_title}</small>
              </summary>

              <div style={{ marginTop: "14px" }}>
                {episode.paragraphs.map((paragraph, index) => (
                  <p key={index} style={{ fontSize: "1.08rem", lineHeight: 1.9 }}>
                    {paragraph}
                  </p>
                ))}
                <p className="role-note">
                  本篇重点字：{episode.focus_characters.length ? episode.focus_characters.join("、") : "—"}
                </p>

                {episode.story_version_id ? (
                  <Link className="button button-secondary" href={`/read/${episode.story_version_id}`}>
                    {episode.status === "completed" ? "重新阅读这一篇" : "进入正式阅读"}
                  </Link>
                ) : episode.status === "current" ? (
                  <Link className="button button-secondary" href="/kids/today">
                    从今日任务正式开始
                  </Link>
                ) : (
                  <p className="catalog-note">
                    当前为预览。正式阅读仍按 Day 1 → Day 30 顺序推进。
                  </p>
                )}
              </div>
            </details>
          ))}
        </div>
      </section>
    </section>
  );
}

export default function ReadingSeriesPage() {
  return (
    <ProtectedPage>
      <ReadingSeriesBrowser />
    </ProtectedPage>
  );
}
