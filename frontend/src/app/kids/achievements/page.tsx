"use client";

import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type AchievementSummary,
  getAchievements,
} from "@/lib/api/client";

const REASONS: Record<string, string> = {
  achievement: "获得新成就",
  completed_review: "完成今日复习",
  completed_reading: "读完一个故事",
  completed_science: "完成科学实验",
  completed_teacher_task: "完成老师的小挑战",
};

function ChildAchievementsContent() {
  const { status, activeChild } = useActiveChild();
  const [summary, setSummary] = useState<AchievementSummary | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setSummary(await getAchievements(activeChild.id));
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "暂时无法打开成就册",
      );
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild) {
    return <section className="child-state"><span className="loading-spinner" /><p>正在打开成就册…</p></section>;
  }

  const starsToGoal = summary?.next_reward_goal
    ? Math.max(0, summary.next_reward_goal.required_stars - summary.star_balance)
    : 0;
  return (
    <section className="child-page achievements-page">
      <header className="achievement-hero">
        <div aria-hidden="true">🏅</div>
        <div><p>认真参与的每一步都值得记住</p><h1>我的成就</h1></div>
        {summary?.stars_enabled ? <strong aria-label={`当前 ${summary.star_balance} 颗星`}>⭐ {summary.star_balance}</strong> : null}
      </header>
      {error ? <div className="child-error" role="alert"><span>🌦️</span><div><strong>成就册暂时合上了</strong><p>{error}</p></div><button onClick={() => void load()} type="button">重新尝试</button></div> : null}
      {!summary ? (
        <div className="child-state compact"><span className="loading-spinner" /><p>正在收集成长时刻…</p></div>
      ) : (
        <>
          {summary.next_reward_goal ? (
            <section className="next-reward-card"><span aria-hidden="true">🎁</span><div><small>下一个家庭奖励</small><h2>{summary.next_reward_goal.title}</h2><p>再收集 {starsToGoal} 颗星，就可以和爸爸妈妈一起完成这个约定。</p></div></section>
          ) : null}
          <section>
            <div className="child-section-heading"><div><span>🌟</span><h2>成长徽章</h2></div><small>{summary.achievements.length} 枚</small></div>
            {summary.achievements.length === 0 ? (
              <div className="child-empty"><span aria-hidden="true">✨</span><strong>第一枚徽章正在路上</strong><p>完成一次真实学习、阅读或实验，就可能遇见它。</p></div>
            ) : (
              <div className="achievement-grid">
                {summary.achievements.map((achievement) => (
                  <article key={achievement.id}><span aria-hidden="true">{achievement.icon}</span><h3>{achievement.title}</h3><p>{achievement.description}</p><small>{new Date(achievement.unlocked_at).toLocaleDateString("zh-CN")}</small></article>
                ))}
              </div>
            )}
          </section>
          {summary.stars_enabled && summary.recent_ledger.length > 0 ? (
            <section className="star-history"><div className="child-section-heading"><div><span>⭐</span><h2>星星足迹</h2></div></div>{summary.recent_ledger.map((entry) => <article key={entry.id}><span>+{entry.amount} ⭐</span><strong>{REASONS[entry.reason_type] ?? "认真参与"}</strong><small>{new Date(entry.occurred_at).toLocaleDateString("zh-CN")}</small></article>)}</section>
          ) : null}
        </>
      )}
      <p className="child-kind-note">星星是对参与和好奇心的鼓励，不是分数，也不会因为不熟悉而减少。</p>
    </section>
  );
}

export default function ChildAchievementsPage() {
  return <ProtectedPage><ChildAchievementsContent /></ProtectedPage>;
}
