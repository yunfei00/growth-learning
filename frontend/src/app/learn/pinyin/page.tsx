"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  getPinyinHistory,
  getPinyinOverview,
  getPinyinPractices,
  getPinyinToday,
  listChildPinyinItems,
  type PinyinHistory,
  type PinyinItem,
  type PinyinKind,
  type PinyinOverview,
  type PinyinState,
  type PinyinToday,
} from "@/lib/api/client";
import { useChildExperienceMode } from "@/lib/experience-mode";

const STATE_LABELS: Record<PinyinState, string> = {
  unlearned: "未学习",
  introduced: "初识",
  practicing: "练习中",
  proficient: "基本掌握",
  stable: "稳定掌握",
};

const KIND_ORDER: PinyinKind[] = ["initial", "final", "tone", "whole"];
const KIND_HELP: Record<PinyinKind, string> = {
  initial: "先听声音，再认识符号",
  final: "听清完整韵母和嘴形变化",
  tone: "用耳朵分辨声音的方向",
  whole: "直接读出来，不拆成普通拼读",
};

function PinyinOverviewContent() {
  const { activeChild, children, setActiveChildId } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [overview, setOverview] = useState<PinyinOverview | null>(null);
  const [items, setItems] = useState<PinyinItem[]>([]);
  const [today, setToday] = useState<PinyinToday | null>(null);
  const [history, setHistory] = useState<PinyinHistory | null>(null);
  const [practiceCount, setPracticeCount] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      const [overviewValue, itemPage, todayValue, historyValue, practices] = await Promise.all([
        getPinyinOverview(activeChild.id),
        listChildPinyinItems(activeChild.id),
        getPinyinToday(activeChild.id),
        getPinyinHistory(activeChild.id),
        getPinyinPractices(),
      ]);
      setOverview(overviewValue);
      setItems(itemPage.items);
      setToday(todayValue);
      setHistory(historyValue);
      setPracticeCount(practices.total);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "拼音学习数据加载失败");
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <main className="pinyin-overview-page section-shell">
      <header className="pinyin-overview-header">
        <div><Link href={childMode ? "/kids/today" : "/learn"}>← {childMode ? "返回今天" : "返回学习"}</Link><p className="eyebrow">语文 · 拼音</p><h1>拼音学习</h1><p>先听，再看，再跟读。每次只学一点点。</p></div>
        {!childMode ? <ChildSwitcher activeChildId={activeChild?.id ?? ""} childOptions={children} onChange={setActiveChildId} /> : null}
      </header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {!overview ? (
        <div className="center-state"><span className="loading-spinner" /><p>正在排好拼音学习路径…</p></div>
      ) : (
        <>
          <section className="pinyin-progress-hero">
            <div><strong>{overview.learned}</strong><span>/ {overview.total}</span><p>已经学习</p></div>
            <div><strong>{overview.stable}</strong><span>/ {overview.total}</span><p>稳定掌握</p></div>
            <p>“学习过”和“稳定掌握”是两件事，慢慢来就很好。</p>
          </section>

          {today?.target_count ? (
            <section className={`pinyin-today-card status-${today.status}`}>
              <header><div><p className="eyebrow">今天 · 约5分钟</p><h2>{today.status === "completed" ? "今日拼音已完成 ✓" : "今天听一听这些声音"}</h2></div><span>{today.completed_count} / {today.target_count}</span></header>
              <div className="pinyin-today-items">
                {[...today.new_items, ...today.review_items].map((item) => (
                  <Link aria-label={`学习拼音 ${item.display_text}`} href={`/learn/pinyin/${item.knowledge_point_id}?source=today`} key={item.knowledge_point_id}>{item.display_text}<small>{STATE_LABELS[item.state_code]}</small></Link>
                ))}
              </div>
              <small>完成后仍然可以重新打开、再次听和再次练习，不会重复计算今日完成数。</small>
            </section>
          ) : null}

          <section className="pinyin-overview-grid" aria-label="拼音分类进度">
            {overview.groups.map((group) => (
              <a href={`#pinyin-${group.kind}`} key={group.kind}>
                <span>{group.label}</span><strong>{group.learned} / {group.total}</strong><small>稳定掌握 {group.stable}</small>
              </a>
            ))}
            <Link href="/learn/pinyin/blending"><span>拼读</span><strong>{STATE_LABELS[overview.blending_state]}</strong><small>{overview.blending_attempts} 次真实练习</small></Link>
          </section>

          <section className="pinyin-path-section">
            <header><div><p className="eyebrow">完整路径</p><h2>点击任意一个开始学习</h2></div><Link href="/learn/pinyin/blending">进入 {practiceCount} 组拼读练习 →</Link></header>
            {KIND_ORDER.map((kind) => {
              const group = overview.groups.find((value) => value.kind === kind);
              return (
                <article id={`pinyin-${kind}`} key={kind}>
                  <div className="pinyin-path-heading"><div><h3>{group?.label}</h3><p>{KIND_HELP[kind]}</p></div><span>{group?.learned} / {group?.total}</span></div>
                  <div className="pinyin-symbol-grid">
                    {items.filter((item) => item.kind === kind).map((item) => (
                      <Link className={`state-${item.state_code}`} href={`/learn/pinyin/${item.knowledge_point_id}?source=path`} key={item.knowledge_point_id}>
                        <strong>{item.display_text}</strong><small>{STATE_LABELS[item.state_code]}</small>
                      </Link>
                    ))}
                  </div>
                </article>
              );
            })}
          </section>

          {!childMode ? <section className="pinyin-history-section">
            <header><div><p className="eyebrow">家长可查看</p><h2>拼音学习记录</h2></div><span>保留陪伴人与评价人</span></header>
            {history?.items.length ? history.items.slice(0, 8).map((session) => (
              <article key={session.session_id}>
                <div><strong>{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(new Date(session.occurred_at))}</strong><span>陪伴人：{session.actor_display_name}</span></div>
                <div>{session.evidence.map((evidence) => <span key={evidence.evidence_id}><b>{evidence.display_text}</b>{evidence.dimension ? `${evidence.dimension} · ` : "学习 · "}{evidence.outcome}</span>)}</div>
              </article>
            )) : <div className="empty-learning-state"><h3>还没有拼音记录</h3><p>听声音不会自动制造记录；完成学习或真实练习后才会显示。</p></div>}
          </section> : null}
        </>
      )}
    </main>
  );
}

export default function PinyinOverviewPage() {
  return <ProtectedPage><PinyinOverviewContent /></ProtectedPage>;
}
