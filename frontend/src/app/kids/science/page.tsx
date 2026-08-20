"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ExperimentSessionPage,
  type ScienceRecommendation,
  listExperimentSessions,
  listScienceRecommendations,
} from "@/lib/api/client";

function ChildScienceContent() {
  const { status, activeChild } = useActiveChild();
  const [recommendations, setRecommendations] = useState<ScienceRecommendation[]>([]);
  const [sessions, setSessions] = useState<ExperimentSessionPage | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      const [recommended, history] = await Promise.all([
        listScienceRecommendations(activeChild.id),
        listExperimentSessions(activeChild.id),
      ]);
      setRecommendations(recommended);
      setSessions(history);
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "科学小屋暂时打不开",
      );
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild) {
    return <section className="child-state"><span className="loading-spinner" /><p>正在准备科学小屋…</p></section>;
  }

  const continuing = sessions?.items.find((item) => item.status === "in_progress");
  return (
    <section className="child-page child-science-page">
      <header className="child-page-heading">
        <span aria-hidden="true">🔬</span>
        <div><p>先猜一猜，再动手找答案</p><h1>科学小屋</h1></div>
      </header>
      {error ? <div className="child-error" role="alert"><span>🌦️</span><div><strong>科学小屋休息了一会儿</strong><p>{error}</p></div><button onClick={() => void load()} type="button">重新尝试</button></div> : null}
      {continuing ? (
        <Link className="child-resume-banner" href={`/science/session/${continuing.id}`}>
          <span aria-hidden="true">🧪</span><div><small>上次做到这里</small><strong>{String(continuing.experiment_snapshot.title ?? "科学探索")}</strong></div><b>继续 →</b>
        </Link>
      ) : null}
      {!sessions ? (
        <div className="child-state compact"><span className="loading-spinner" /><p>正在寻找今天的探索…</p></div>
      ) : recommendations.length === 0 ? (
        <div className="child-empty"><span aria-hidden="true">🌱</span><strong>新的探索正在准备中</strong><p>稍后和爸爸妈妈再来看看吧。</p></div>
      ) : (
        <div className="child-science-grid">
          {recommendations.slice(0, 6).map(({ experiment, ready_at_home: ready }) => (
            <Link className="child-science-card" href={`/science/${experiment.id}`} key={experiment.id}>
              <span aria-hidden="true">{ready ? "🧪" : "🔎"}</span><small>{experiment.estimated_duration_minutes} 分钟</small>
              <h2>{experiment.title}</h2><p>{experiment.guiding_question}</p><strong>{ready ? "开始探索 →" : "和家长一起准备 →"}</strong>
            </Link>
          ))}
        </div>
      )}
      <p className="child-kind-note">实验需要大人陪伴。孩子模式不显示家庭材料设置，也不展示家长记录。</p>
    </section>
  );
}

export default function ChildSciencePage() {
  return <ProtectedPage><ChildScienceContent /></ProtectedPage>;
}
