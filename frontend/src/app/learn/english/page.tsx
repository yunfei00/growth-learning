"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { EnglishVisualCard } from "@/components/english-visual";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  getEnglishHistory,
  getEnglishOverview,
  getEnglishToday,
  listChildEnglishItems,
  type EnglishHistory,
  type EnglishItem,
  type EnglishKind,
  type EnglishOverview,
  type EnglishState,
  type EnglishToday,
} from "@/lib/api/client";
import { useChildExperienceMode } from "@/lib/experience-mode";

const KIND_ORDER: EnglishKind[] = ["word", "letter", "phonics", "phrase"];
const STATE_LABELS: Record<EnglishState, string> = {
  unlearned: "未学习",
  introduced: "初次接触",
  practicing: "练习中",
  proficient: "基本掌握",
  stable: "稳定掌握",
};

function EnglishOverviewContent() {
  const { activeChild, children, setActiveChildId } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [overview, setOverview] = useState<EnglishOverview | null>(null);
  const [items, setItems] = useState<EnglishItem[]>([]);
  const [today, setToday] = useState<EnglishToday | null>(null);
  const [history, setHistory] = useState<EnglishHistory | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      const [overviewValue, itemPage, todayValue, historyValue] = await Promise.all([
        getEnglishOverview(activeChild.id),
        listChildEnglishItems(activeChild.id),
        getEnglishToday(activeChild.id),
        getEnglishHistory(activeChild.id),
      ]);
      setOverview(overviewValue);
      setItems(itemPage.items);
      setToday(todayValue);
      setHistory(historyValue);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "英语学习数据加载失败");
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const categories = useMemo(() => {
    const result = new Map<string, EnglishItem[]>();
    for (const item of items) {
      const key = `${item.kind}:${item.category}`;
      result.set(key, [...(result.get(key) ?? []), item]);
    }
    return result;
  }, [items]);

  return (
    <main className="english-overview-page section-shell">
      <header className="english-overview-header">
        <div>
          <Link href={childMode ? "/kids/today" : "/learn"}>← {childMode ? "返回今天" : "返回学习"}</Link>
          <p className="eyebrow">English · 听懂优先</p>
          <h1>英语声音乐园</h1>
          <p>先听声音、看图片和动作，再慢慢连接单词、字母与拼读。</p>
        </div>
        {!childMode ? <ChildSwitcher activeChildId={activeChild?.id ?? ""} childOptions={children} onChange={setActiveChildId} /> : null}
      </header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {!overview ? <div className="center-state"><span className="loading-spinner" /><p>正在准备英语声音和图片…</p></div> : <>
        <section className="english-progress-hero">
          <div><strong>{overview.understood_words}</strong><span>个</span><p>能听懂的词汇</p></div>
          <div><strong>{overview.letters_learned}</strong><span>/ {overview.letters_total}</span><p>接触过的字母</p></div>
          <div><strong>{overview.phonics_practicing}</strong><span>项</span><p>正在体验的拼读</p></div>
          <p>听懂、会说、字母和拼读分别记录，不用一个总分评价孩子。</p>
        </section>

        {today?.target_count ? <section className={`english-today-card status-${today.status}`}>
          <header><div><p className="eyebrow">今天 · 约 {today.estimated_minutes} 分钟</p><h2>{today.status === "completed" ? "今日英语已完成 ✓" : "今天先听一听"}</h2></div><span>{today.completed_count} / {today.target_count}</span></header>
          <div className="english-today-items">{today.items.map((item) => <Link className={`state-${item.state_code}`} href={`/learn/english/${item.knowledge_point_id}?source=today&count=${item.exercise_count}`} key={item.knowledge_point_id}><EnglishVisualCard compact label={item.meaning_zh} visual={item.visual} /><div><strong>{item.completed ? `${item.text} ✓` : item.item_kind === "review" ? "再听一听" : "新声音"}</strong><small>{item.completed ? "已完成 · 可以再练" : `${item.category_label} · ${item.exercise_count} 个小问题`}</small></div></Link>)}</div>
        </section> : null}

        <section aria-label="英语能力进度" className="english-kind-overview">
          {overview.groups.map((group) => <a className={`state-${group.state_code}`} href={`#english-${group.kind}`} key={group.kind}><span>{group.label}</span><strong>{STATE_LABELS[group.state_code]}</strong><small>已学习 {group.learned} / {group.total}</small></a>)}
        </section>

        <section className="english-path-section">
          <header><div><p className="eyebrow">完整路径</p><h2>点一个声音开始探索</h2></div><span>{overview.catalog_version}</span></header>
          {KIND_ORDER.map((kind) => {
            const group = overview.groups.find((value) => value.kind === kind);
            const kindCategories = [...categories.entries()].filter(([key]) => key.startsWith(`${kind}:`));
            if (!group || !kindCategories.length) return null;
            return <article id={`english-${kind}`} key={kind}>
              <div className="english-path-heading"><div><h3>{group.label}</h3><p>{kind === "word" ? "先听懂常见词，再在生活里使用。" : kind === "letter" ? "字母名称和字母声音分开学习。" : kind === "phonics" ? "从可靠的示例词和 CVC 拼读开始。" : "在动作和场景里听懂整句话。"}</p></div><span>{group.learned} / {group.total}</span></div>
              {kindCategories.map(([key, values]) => <section className="english-category" key={key}><h4>{values[0].category_label}</h4><div className="english-item-grid">{values.map((item) => <Link aria-label={`${item.text}，${STATE_LABELS[item.state_code]}`} className={`state-${item.state_code}`} href={`/learn/english/${item.knowledge_point_id}?source=path`} key={item.knowledge_point_id}><EnglishVisualCard compact label={item.meaning_zh} visual={item.visual} /><strong>{item.text}</strong><small>{STATE_LABELS[item.state_code]}</small></Link>)}</div></section>)}
            </article>;
          })}
        </section>

        {!childMode ? <section className="english-history-section"><header><div><p className="eyebrow">家长可查看</p><h2>英语学习记录</h2></div><span>练习与独立检查分开保存</span></header>{history?.items.length ? history.items.slice(0, 8).map((entry) => <article key={entry.session_id}><div><strong>{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(new Date(entry.occurred_at))}</strong><span>陪伴：{entry.actor_display_name}</span><small>{entry.mode === "assessment" ? "独立检查" : entry.mode === "observation" ? "口语观察" : "练习"}</small></div>{entry.evidence.map((evidence) => <div key={`${entry.session_id}-${evidence.knowledge_point_id}`}><b>{evidence.text}</b><span>{evidence.speaking_observations ? "家长记录了一次口语表现" : `${evidence.problem_count}题 · 独立正确 ${evidence.correct} · 提示后 ${evidence.hinted_correct}`}</span><small>{evidence.dimension}</small></div>)}</article>) : <div className="empty-learning-state"><h3>还没有英语记录</h3><p>开始听声音和看图片后，这里会保留真实过程。</p></div>}</section> : null}
      </>}
    </main>
  );
}

export default function EnglishOverviewPage() {
  return <ProtectedPage><EnglishOverviewContent /></ProtectedPage>;
}
