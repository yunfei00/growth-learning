"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { ApiClientError, type ScienceExperiment, createClientKey, getScienceExperiment, startExperimentSession } from "@/lib/api/client";

function ExperimentDetail() {
  const params = useParams<{ experimentId: string }>();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const [experiment, setExperiment] = useState<ScienceExperiment | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const startRequestKey = useRef<string | null>(null);
  useEffect(() => { if (params.experimentId) getScienceExperiment(params.experimentId).then(setExperiment).catch((reason) => setError(reason instanceof ApiClientError ? reason.message : "无法加载实验")); }, [params.experimentId]);
  if (!activeChild || !experiment) return <section className="center-state section-shell">{error ? <p className="form-message form-error">{error}</p> : <><span className="loading-spinner" /><p>正在打开实验卡…</p></>}</section>;
  const start = async () => {
    setWorking(true);
    setError("");
    try {
      startRequestKey.current ??= createClientKey();
      const session = await startExperimentSession(
        activeChild.id,
        experiment.id,
        startRequestKey.current,
      );
      router.push(`/science/session/${session.id}`);
    } catch (reason) {
      console.error("Failed to start science experiment", {
        status: reason instanceof ApiClientError ? reason.status : undefined,
        response: reason instanceof ApiClientError ? reason.response : undefined,
        error: reason,
      });
      setError("实验暂时无法开始，请稍后重试。");
      setWorking(false);
    }
  };
  return <section className="science-detail section-shell">
    <Link href="/science">← 返回实验室</Link>
    <header><p className="eyebrow">{experiment.age_min}–{experiment.age_max ?? "不限"} 岁 · {experiment.estimated_duration_minutes} 分钟</p><h1>{experiment.title}</h1><p>{experiment.description}</p></header>
    {error ? <p className="form-message form-error">{error}</p> : null}
    <div className="experiment-prep-grid">
      <article><p className="eyebrow">先问孩子</p><h2>{experiment.guiding_question}</h2><p>先让孩子说出自己的预测，再开始动手。</p></article>
      <article><p className="eyebrow">家长准备</p><h2>材料</h2><ul>{experiment.requirements.map((item) => <li key={item.id}>{item.material.name} {item.quantity_text ? `· ${item.quantity_text}` : ""}{!item.is_required ? "（可选）" : ""}</li>)}</ul></article>
      <article><p className="eyebrow">安全提醒</p><h2>成人全程陪伴</h2><ul>{experiment.safety_notes.map((note) => <li key={note}>{note}</li>)}</ul></article>
    </div>
    <button className="button button-primary experiment-start" disabled={working} type="button" onClick={() => void start()}>{working ? "正在建立实验记录…" : "开始实验"}</button>
  </section>;
}

export default function ExperimentDetailPage() { return <ProtectedPage><ExperimentDetail /></ProtectedPage>; }
