"use client";
/* eslint-disable @next/next/no-img-element -- private authenticated media cannot use Next's public optimizer */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ExperimentEvidence,
  type ExperimentGrowthCard,
  type ExperimentSession,
  addExperimentEvidence,
  completeExperiment,
  createClientKey,
  generateExperimentStory,
  getApiBaseUrl,
  getExperimentGrowthCard,
  getExperimentSession,
  updateExperimentSession,
  uploadExperimentMedia,
} from "@/lib/api/client";

const STEPS: Array<{ key: ExperimentSession["current_step"]; label: string }> = [
  { key: "question", label: "提出问题" }, { key: "prediction", label: "孩子预测" },
  { key: "materials", label: "准备材料" }, { key: "experiment", label: "动手实验" },
  { key: "observation", label: "记录观察" }, { key: "explanation", label: "一起解释" },
  { key: "follow_up", label: "继续追问" }, { key: "summary", label: "孩子总结" },
];

const EVIDENCE: Array<{ value: ExperimentEvidence["evidence_type"]; label: string; tags: string[] }> = [
  { value: "prediction", label: "孩子的预测", tags: ["prediction"] },
  { value: "observation", label: "观察到了什么", tags: ["observation", "hands_on"] },
  { value: "child_original_words", label: "孩子的原话", tags: ["expression"] },
  { value: "question_asked", label: "孩子提出的问题", tags: ["questioning"] },
  { value: "child_summary", label: "孩子自己的总结", tags: ["causal_reasoning", "expression"] },
];

function messageFrom(error: unknown, fallback: string) { return error instanceof ApiClientError ? error.message : fallback; }

function ExperimentRunner() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { activeChild, family } = useActiveChild();
  const [session, setSession] = useState<ExperimentSession | null>(null);
  const [growth, setGrowth] = useState<ExperimentGrowthCard | null>(null);
  const [type, setType] = useState<ExperimentEvidence["evidence_type"]>("prediction");
  const [text, setText] = useState("");
  const [parentNote, setParentNote] = useState("");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!activeChild || !params.sessionId) return;
    try {
      const value = await getExperimentSession(activeChild.id, params.sessionId);
      setSession(value); setParentNote(value.parent_note ?? ""); setError("");
      if (value.status === "completed") setGrowth(await getExperimentGrowthCard(activeChild.id, value.id));
    } catch (reason) { setError(messageFrom(reason, "无法加载实验记录")); }
  }, [activeChild, params.sessionId]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  if (!activeChild || !session) return <section className="center-state section-shell">{error ? <p className="form-message form-error">{error}</p> : <><span className="loading-spinner" /><p>正在恢复实验进度…</p></>}</section>;
  const snapshot = session.experiment_snapshot;
  const title = String(snapshot.title ?? "科学实验");
  const move = async (step: ExperimentSession["current_step"]) => { setWorking(true); try { setSession(await updateExperimentSession(activeChild.id, session.id, { action: "advance", current_step: step })); setMessage("进度已保存，可以随时离开后继续。"); } catch (reason) { setError(messageFrom(reason, "进度保存失败")); } finally { setWorking(false); } };
  const record = async () => { if (!text.trim()) return; setWorking(true); try { const config = EVIDENCE.find((item) => item.value === type)!; await addExperimentEvidence(activeChild.id, session.id, [{ evidence_type: type, original_text: text.trim(), capability_tags: config.tags, client_key: createClientKey() }]); setText(""); await load(); setMessage("孩子的原话已原样保存。"); } catch (reason) { setError(messageFrom(reason, "记录保存失败")); } finally { setWorking(false); } };
  const upload = async (file?: File) => { if (!file) return; setWorking(true); try { setSession(await uploadExperimentMedia(activeChild.id, session.id, file)); setMessage("媒体已保存到家庭私有空间。"); } catch (reason) { setError(messageFrom(reason, "媒体上传失败")); } finally { setWorking(false); } };
  const finish = async () => { setWorking(true); try { const completed = await completeExperiment(activeChild.id, session.id, parentNote); setSession(completed); setGrowth(await getExperimentGrowthCard(activeChild.id, session.id)); setMessage("实验完成。只记录接触证据，没有自动产生认字答对记录。"); } catch (reason) { setError(messageFrom(reason, "无法完成实验")); } finally { setWorking(false); } };
  const story = async () => { setWorking(true); try { const result = await generateExperimentStory(activeChild.id, session.id); router.push(`/read/${result.version.id}`); } catch (reason) { setError(messageFrom(reason, "实验故事暂时无法生成")); setWorking(false); } };
  return <section className="science-session section-shell">
    <div className="reader-topbar"><Link href="/science">← 实验室</Link><span>{session.status === "completed" ? "已完成" : "进度自动保存"}</span></div>
    <header><p className="eyebrow">家庭陪伴实验 · {session.local_date}</p><h1>{title}</h1><p>{String(snapshot.guiding_question ?? "先听听孩子怎么想。")}</p></header>
    {error ? <p className="form-message form-error">{error}</p> : null}{message ? <p className="form-message form-success">{message}</p> : null}
    {session.status !== "completed" ? <>
      <nav className="experiment-steps" aria-label="实验步骤">{STEPS.map((item, index) => <button className={session.current_step === item.key ? "active" : ""} disabled={working} key={item.key} onClick={() => void move(item.key)} type="button"><small>{index + 1}</small>{item.label}</button>)}</nav>
      <div className="experiment-guidance"><article><p className="eyebrow">预期现象</p><p>{String(snapshot.expected_phenomenon ?? "")}</p></article><article><p className="eyebrow">家长解释</p><p>{String(snapshot.parent_scientific_explanation ?? "")}</p></article></div>
      <section className="evidence-capture"><h2>记录真实探索</h2><p>保留孩子的原话与观察。标签只描述行为，不生成分数。</p><div className="evidence-form"><select value={type} onChange={(event) => setType(event.target.value as ExperimentEvidence["evidence_type"])}>{EVIDENCE.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="尽量逐字记录孩子当时说的话…" /><button className="button button-primary" disabled={working || !text.trim()} onClick={() => void record()} type="button">保存原始记录</button></div>
        <div className="evidence-list">{session.evidence.map((item) => <article key={item.id}><span>{EVIDENCE.find((row) => row.value === item.evidence_type)?.label ?? item.evidence_type}</span><p>{item.original_text}</p><small>{item.capability_tags.join(" · ")}</small></article>)}</div>
      </section>
      <section className="media-capture"><h2>照片、视频或语音</h2><p>媒体不会公开，只通过家庭鉴权入口读取。</p><label className="button button-secondary">选择媒体<input hidden type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/*" onChange={(event) => void upload(event.target.files?.[0])} /></label><div className="experiment-media-grid">{session.media.map((item) => item.media_kind === "image" ? <img alt="实验记录" key={item.id} src={`${getApiBaseUrl()}${item.content_url}`} /> : item.media_kind === "video" ? <video controls key={item.id} src={`${getApiBaseUrl()}${item.content_url}`} /> : <audio controls key={item.id} src={`${getApiBaseUrl()}${item.content_url}`} />)}</div></section>
      {family?.current_role === "admin" ? <label className="parent-note">家长备注<textarea value={parentNote} onChange={(event) => setParentNote(event.target.value)} /></label> : null}
      <button className="button button-primary experiment-finish" disabled={working} onClick={() => void finish()} type="button">完成实验并生成成长卡</button>
    </> : growth ? <section className="growth-card"><p className="eyebrow">科学成长记录</p><h2>{growth.title}</h2><p>陪伴者：{growth.accompanying_user}</p><div className="growth-evidence-grid"><article><strong>预测</strong>{growth.prediction.map((line) => <p key={line}>{line}</p>)}</article><article><strong>观察</strong>{growth.observation.map((line) => <p key={line}>{line}</p>)}</article><article><strong>孩子原话</strong>{growth.child_original_words.map((line) => <p key={line}>{line}</p>)}</article><article><strong>科学解释</strong><p>{growth.scientific_explanation}</p></article></div><p className="evidence-note">本记录不包含科学能力分数；完成实验仅产生知识接触证据。</p>{family?.current_role === "admin" ? <button className="button button-primary" disabled={working} onClick={() => void story()} type="button">用这次实验生成识字故事</button> : null}</section> : null}
  </section>;
}

export default function ExperimentSessionPage() { return <ProtectedPage><ExperimentRunner /></ProtectedPage>; }
