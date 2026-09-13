"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  type ReadingCheckinDay,
  type ReadingCheckinSummary,
  getReadingCheckins,
} from "@/lib/reading-checkin-api";
import {
  type ReadingSeriesProgress,
  getCurrentReadingSeries,
} from "@/lib/reading-series-api";

function localDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function monthBounds(value: Date): { from: string; to: string } {
  const from = new Date(value.getFullYear(), value.getMonth(), 1, 12);
  const to = new Date(value.getFullYear(), value.getMonth() + 1, 0, 12);
  return { from: localDate(from), to: localDate(to) };
}

function durationLabel(seconds: number): string {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`;
}

function CheckinCalendar() {
  const { status, children, activeChild, setActiveChildId } = useActiveChild();
  const [month, setMonth] = useState(() => new Date());
  const [summary, setSummary] = useState<ReadingCheckinSummary | null>(null);
  const [series, setSeries] = useState<ReadingSeriesProgress | null>(null);
  const [selected, setSelected] = useState<ReadingCheckinDay | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    const bounds = monthBounds(month);
    try {
      const [checkins, readingSeries] = await Promise.all([
        getReadingCheckins(activeChild.id, {
          ...bounds,
          today: localDate(new Date()),
        }),
        getCurrentReadingSeries(activeChild.id),
      ]);
      setSummary(checkins);
      setSeries(readingSeries);
      setSelected(checkins.days.find((item) => item.date === localDate(new Date())) ?? null);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "暂时无法读取阅读记录");
    }
  }, [activeChild, month]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const dayByDate = useMemo(
    () => new Map(summary?.days.map((item) => [item.date, item]) ?? []),
    [summary],
  );

  if (status !== "ready" || !activeChild) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在整理阅读记录…</p></section>;
  }

  const first = new Date(month.getFullYear(), month.getMonth(), 1, 12);
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0, 12);
  const cells: Array<{ key: string; label: number | null; date: string | null }> = [];
  for (let index = 0; index < first.getDay(); index += 1) {
    cells.push({ key: `blank-${index}`, label: null, date: null });
  }
  for (let day = 1; day <= last.getDate(); day += 1) {
    const value = new Date(month.getFullYear(), month.getMonth(), day, 12);
    cells.push({ key: localDate(value), label: day, date: localDate(value) });
  }

  return (
    <section className="reading-hub section-shell">
      <div className="dashboard-toolbar">
        <div>
          <p className="eyebrow">每日阅读</p>
          <h1>阅读打卡</h1>
          <p className="role-note">每天认真读一点就好。求助字只用来了解阅读过程，不会直接改变识字掌握度。</p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={(id) => {
            setSummary(null);
            setSeries(null);
            setSelected(null);
            setActiveChildId(id);
          }}
        />
      </div>

      <div className="reader-topbar">
        <Link href="/read">← 返回故事书</Link>
        <Link href="/kids/today">📖 打开今日任务</Link>
      </div>

      {error ? <p className="form-message form-error">{error}</p> : null}

      <div className="reading-summary-grid">
        <article><span>今天</span><strong>{summary?.today_completed ? "✅ 已完成" : "待阅读"}</strong></article>
        <article><span>连续阅读</span><strong>{summary?.current_streak ?? 0} 天</strong></article>
        <article><span>本月完成</span><strong>{summary?.completed_days ?? 0} 天</strong></article>
        <article><span>本月阅读</span><strong>{durationLabel(summary?.total_duration_seconds ?? 0)}</strong></article>
      </div>

      {series ? (
        <section className="story-generator-panel">
          <div className="section-title-row">
            <div>
              <p className="eyebrow">30 天连续故事 · 第一季</p>
              <h2>{series.title}</h2>
            </div>
            <strong>{series.completed_episodes} / {series.total_episodes} 天</strong>
          </div>
          <progress
            aria-label="连续故事阅读进度"
            max={series.total_episodes}
            style={{ width: "100%", height: "16px" }}
            value={series.completed_episodes}
          />
          <p className="role-note">
            {series.current_episode_number
              ? `当前：第 ${series.current_episode_number} 天 · ${series.current_chapter_title} · ${series.current_episode_title}`
              : "🎉 第一季已经全部读完。"}
          </p>
          {series.current_story_version_id ? (
            <Link className="button button-primary" href={`/read/${series.current_story_version_id}`}>继续今天的故事</Link>
          ) : series.current_episode_number ? (
            <Link className="button button-primary" href="/kids/today">从今日任务开始</Link>
          ) : null}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "10px", marginTop: "18px" }}>
            {series.episodes.map((episode) => {
              const marker = episode.status === "completed" ? "✅" : episode.status === "in_progress" || episode.status === "current" ? "📖" : "○";
              const card = (
                <div style={{ border: "1px solid currentColor", borderRadius: "14px", padding: "12px", minHeight: "94px" }}>
                  <strong>{marker} 第 {episode.episode_number} 天</strong>
                  <small style={{ display: "block", marginTop: "4px" }}>{episode.chapter_title}</small>
                  <span style={{ display: "block", marginTop: "6px" }}>{episode.title}</span>
                </div>
              );
              return episode.story_version_id ? <Link href={`/read/${episode.story_version_id}`} key={episode.episode_number}>{card}</Link> : <div key={episode.episode_number}>{card}</div>;
            })}
          </div>
        </section>
      ) : null}

      <section className="story-generator-panel">
        <div className="section-title-row">
          <div><p className="eyebrow">阅读日历</p><h2>{month.getFullYear()} 年 {month.getMonth() + 1} 月</h2></div>
          <span>本月求助 {summary?.total_help_count ?? 0} 次</span>
        </div>
        <div className="mode-buttons">
          <button onClick={() => setMonth((current) => new Date(current.getFullYear(), current.getMonth() - 1, 1, 12))} type="button">← 上个月</button>
          <button onClick={() => setMonth(new Date())} type="button">本月</button>
          <button onClick={() => setMonth((current) => new Date(current.getFullYear(), current.getMonth() + 1, 1, 12))} type="button">下个月 →</button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr))", gap: "8px", marginTop: "18px" }}>
          {["日", "一", "二", "三", "四", "五", "六"].map((label) => <strong key={label} style={{ textAlign: "center", padding: "8px" }}>{label}</strong>)}
          {cells.map((cell) => {
            if (!cell.date || cell.label === null) return <span key={cell.key} />;
            const record = dayByDate.get(cell.date);
            const isToday = cell.date === localDate(new Date());
            return (
              <button
                key={cell.key}
                onClick={() => setSelected(record ?? null)}
                style={{ minHeight: "64px", borderRadius: "14px", border: "1px solid currentColor", background: "transparent", cursor: "pointer" }}
                type="button"
              >
                <strong>{cell.label}</strong><br />
                <span>{record?.completed ? "✅" : isToday ? "📖" : "·"}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="story-generator-panel">
        <div className="section-title-row"><div><p className="eyebrow">当天记录</p><h2>{selected?.date ?? "点日历查看"}</h2></div></div>
        {selected ? (
          <div>
            <p><strong>{selected.completed ? "✅ 已完成" : "阅读未完成"}</strong>{selected.title ? ` · ${selected.title}` : ""}</p>
            <p>阅读方式：{selected.reading_mode === "independent" ? "孩子自主阅读" : selected.reading_mode === "with_help" ? "家长陪读" : "尚未开始"}</p>
            <p>阅读时长：{selected.duration_seconds == null ? "—" : durationLabel(selected.duration_seconds)}</p>
            <p>点字求助：{selected.help_count} 次{selected.help_characters.length ? `（${selected.help_characters.join("、")}）` : ""}</p>
            {selected.story_version_id ? <Link className="button button-secondary" href={`/read/${selected.story_version_id}`}>打开当天故事</Link> : null}
          </div>
        ) : <p>这一天还没有阅读任务记录。</p>}
      </section>
    </section>
  );
}

export default function ReadingCheckinsPage() {
  return <ProtectedPage><CheckinCalendar /></ProtectedPage>;
}
