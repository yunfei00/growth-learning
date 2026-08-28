"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  getMathHistory,
  getMathOverview,
  getMathToday,
  listChildMathSkills,
  type MathHistory,
  type MathOverview,
  type MathSkill,
  type MathState,
  type MathToday,
} from "@/lib/api/client";
import { useChildExperienceMode } from "@/lib/experience-mode";

const STATE_LABELS: Record<MathState, string> = {
  unlearned: "未学习",
  introduced: "初步理解",
  practicing: "练习中",
  proficient: "能够独立完成",
  stable: "稳定掌握",
};

const DOMAIN_ORDER = [
  "classification",
  "quantity",
  "number_symbol",
  "comparison",
  "sequence",
  "composition",
  "operation",
  "pattern",
  "geometry",
  "spatial",
  "measurement",
];

function MathOverviewContent() {
  const { activeChild, children, setActiveChildId } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [overview, setOverview] = useState<MathOverview | null>(null);
  const [skills, setSkills] = useState<MathSkill[]>([]);
  const [today, setToday] = useState<MathToday | null>(null);
  const [history, setHistory] = useState<MathHistory | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      const [overviewValue, skillPage, todayValue, historyValue] = await Promise.all([
        getMathOverview(activeChild.id),
        listChildMathSkills(activeChild.id),
        getMathToday(activeChild.id),
        getMathHistory(activeChild.id),
      ]);
      setOverview(overviewValue);
      setSkills(skillPage.items);
      setToday(todayValue);
      setHistory(historyValue);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "数学学习数据加载失败");
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <main className="math-overview-page section-shell">
      <header className="math-overview-header">
        <div>
          <Link href={childMode ? "/kids/today" : "/learn"}>← {childMode ? "返回今天" : "返回学习"}</Link>
          <p className="eyebrow">数学 · 启蒙</p>
          <h1>数学成长</h1>
          <p>先看懂数量和关系，再慢慢学会用数字表示。</p>
        </div>
        {!childMode ? <ChildSwitcher activeChildId={activeChild?.id ?? ""} childOptions={children} onChange={setActiveChildId} /> : null}
      </header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {!overview ? <div className="center-state"><span className="loading-spinner" /><p>正在排好数学学习路径…</p></div> : <>
        <section className="math-progress-hero">
          <div><strong>{overview.learned}</strong><span>/ {overview.total}</span><p>接触过的数学能力</p></div>
          <div><strong>{overview.stable}</strong><span>/ {overview.total}</span><p>跨时间稳定掌握</p></div>
          <p>这里没有数学总分，也不按速度和同龄排名评价孩子。</p>
        </section>

        {today?.target_count ? <section className={`math-today-card status-${today.status}`}>
          <header><div><p className="eyebrow">今天 · 约{today.estimated_minutes}分钟</p><h2>{today.status === "completed" ? "今日数学已完成 ✓" : "今天动手想一想"}</h2></div><span>{today.completed_count} / {today.target_count}</span></header>
          <div className="math-today-items">{today.items.map((item) => <Link className={`state-${item.state_code}`} href={`/learn/math/${item.knowledge_point_id}?source=today&count=${item.problem_count}`} key={item.knowledge_point_id}><strong>{item.title}</strong><small>{item.problem_count}题 · {STATE_LABELS[item.state_code]}</small>{item.completed ? <b>已完成 ✓ · 可以再练</b> : null}</Link>)}</div>
        </section> : null}

        <section aria-label="数学领域进度" className="math-domain-overview">
          {overview.groups.map((group) => <a className={`state-${group.state_code}`} href={`#math-${group.domain}`} key={group.domain}><span>{group.label}</span><strong>{STATE_LABELS[group.state_code]}</strong><small>已学习 {group.learned} / {group.total}</small></a>)}
        </section>

        <section className="math-path-section">
          <header><div><p className="eyebrow">完整路径</p><h2>点击任意一个能力开始</h2></div><span>课程 Skill 1 / {overview.total} 起步</span></header>
          {DOMAIN_ORDER.map((domain) => {
            const group = overview.groups.find((item) => item.domain === domain);
            const domainSkills = skills.filter((item) => item.domain === domain);
            if (!group || !domainSkills.length) return null;
            return <article id={`math-${domain}`} key={domain}>
              <div className="math-path-heading"><div><h3>{group.label}</h3><p>一次重点学习一个能力，前置路径不会硬锁。</p></div><span>{group.learned} / {group.total}</span></div>
              <div className="math-skill-grid">{domainSkills.map((skill) => <Link className={`state-${skill.state_code}`} href={`/learn/math/${skill.knowledge_point_id}?source=path`} key={skill.knowledge_point_id}><span aria-hidden="true">{skill.order_index + 1}</span><strong>{skill.title}</strong><small>{STATE_LABELS[skill.state_code]}</small></Link>)}</div>
            </article>;
          })}
        </section>

        {!childMode ? <section className="math-history-section">
          <header><div><p className="eyebrow">家长可查看</p><h2>数学学习记录</h2></div><span>按日期、Session 和 Skill 组织</span></header>
          {history?.items.length ? history.items.slice(0, 8).map((item) => <article key={item.session_id}><div><strong>{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(new Date(item.occurred_at))}</strong><span>陪伴：{item.actor_display_name}</span><small>{item.mode === "assessment" ? "独立测评" : item.mode === "offline" ? "动手活动" : "练习"}</small></div>{item.skills.map((skill) => <div key={skill.knowledge_point_id}><b>{skill.title}</b><span>{item.mode === "offline" ? "动手操作一次" : `${skill.problem_count}题 · 独立正确 ${skill.correct} · 提示后 ${skill.hinted_correct}`}</span><small>{skill.representations.join(" · ")}</small></div>)}</article>) : <div className="empty-learning-state"><h3>还没有数学记录</h3><p>开始动手练习后，这里会保留题目级真实过程。</p></div>}
        </section> : null}
      </>}
    </main>
  );
}

export default function MathOverviewPage() {
  return <ProtectedPage><MathOverviewContent /></ProtectedPage>;
}
