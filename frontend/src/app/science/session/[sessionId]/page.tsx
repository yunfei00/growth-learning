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
  deleteExperimentMedia,
  generateExperimentAIParentTip,
  generateExperimentStory,
  getApiBaseUrl,
  getExperimentGrowthCard,
  getExperimentSession,
  replaceExperimentMedia,
  updateExperimentEvidence,
  updateExperimentSession,
  uploadExperimentMedia,
} from "@/lib/api/client";

const STEPS: Array<{ key: ExperimentSession["current_step"]; label: string }> = [
  { key: "question", label: "提出问题" },
  { key: "prediction", label: "孩子预测" },
  { key: "materials", label: "准备材料" },
  { key: "experiment", label: "动手实验" },
  { key: "observation", label: "记录观察" },
  { key: "explanation", label: "一起解释" },
  { key: "follow_up", label: "继续追问" },
  { key: "summary", label: "孩子总结" },
];

const EVIDENCE: Array<{
  value: ExperimentEvidence["evidence_type"];
  label: string;
  tags: string[];
}> = [
  { value: "prediction", label: "孩子的预测", tags: ["prediction"] },
  { value: "observation", label: "实验现象 / 观察", tags: ["observation", "hands_on"] },
  { value: "child_original_words", label: "孩子的原话", tags: ["expression"] },
  { value: "question_asked", label: "孩子提出的问题", tags: ["questioning"] },
  { value: "child_summary", label: "孩子自己的总结", tags: ["causal_reasoning", "expression"] },
];

function messageFrom(error: unknown, fallback: string) {
  return error instanceof ApiClientError ? error.message : fallback;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function ExperimentRunner() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const { activeChild, family } = useActiveChild();
  const [session, setSession] = useState<ExperimentSession | null>(null);
  const [growth, setGrowth] = useState<ExperimentGrowthCard | null>(null);
  const [type, setType] = useState<ExperimentEvidence["evidence_type"]>("prediction");
  const [text, setText] = useState("");
  const [editingEvidenceId, setEditingEvidenceId] = useState("");
  const [editingEvidenceText, setEditingEvidenceText] = useState("");
  const [parentNote, setParentNote] = useState("");
  const [aiTip, setAiTip] = useState("");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild || !params.sessionId) return;
    try {
      const value = await getExperimentSession(activeChild.id, params.sessionId);
      setSession(value);
      setParentNote(value.parent_note ?? "");
      setError("");
      if (value.status === "completed") {
        setGrowth(await getExperimentGrowthCard(activeChild.id, value.id));
      }
    } catch (reason) {
      setError(messageFrom(reason, "无法加载实验记录"));
    }
  }, [activeChild, params.sessionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (!activeChild || !session) {
    return (
      <section className="center-state section-shell">
        {error ? (
          <p className="form-message form-error">{error}</p>
        ) : (
          <><span className="loading-spinner" /><p>正在恢复实验进度…</p></>
        )}
      </section>
    );
  }

  const snapshot = session.experiment_snapshot;
  const title = String(snapshot.title ?? "科学实验");
  const editable = session.status === "in_progress" || session.status === "completed";

  const run = async (action: () => Promise<void>, fallback: string) => {
    setWorking(true);
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(messageFrom(reason, fallback));
    } finally {
      setWorking(false);
    }
  };

  const move = (step: ExperimentSession["current_step"]) => run(async () => {
    setSession(await updateExperimentSession(activeChild.id, session.id, {
      action: "advance",
      current_step: step,
    }));
    setMessage("进度已保存，可以随时离开后继续。");
  }, "进度保存失败");

  const record = () => run(async () => {
    if (!text.trim()) return;
    const config = EVIDENCE.find((item) => item.value === type)!;
    await addExperimentEvidence(activeChild.id, session.id, [{
      evidence_type: type,
      original_text: text.trim(),
      capability_tags: config.tags,
      client_key: createClientKey(),
    }]);
    setText("");
    await load();
    setMessage(session.status === "completed" ? "实验档案已补充。" : "孩子的原话已原样保存。");
  }, "记录保存失败");

  const saveEvidence = (evidence: ExperimentEvidence) => run(async () => {
    if (!editingEvidenceText.trim()) return;
    await updateExperimentEvidence(activeChild.id, session.id, evidence.id, {
      original_text: editingEvidenceText.trim(),
    });
    setEditingEvidenceId("");
    setEditingEvidenceText("");
    await load();
    setMessage("实验现象或孩子回答已更新，完成状态保持不变。");
  }, "记录修改失败");

  const upload = (file?: File) => run(async () => {
    if (!file) return;
    setSession(await uploadExperimentMedia(activeChild.id, session.id, file));
    setMessage("照片已持久保存到家庭私有空间。");
  }, "媒体上传失败");

  const replace = (mediaId: string, file?: File) => run(async () => {
    if (!file) return;
    setSession(await replaceExperimentMedia(activeChild.id, session.id, mediaId, file));
    setMessage("照片已替换，实验完成状态保持不变。");
  }, "媒体替换失败");

  const remove = (mediaId: string) => run(async () => {
    if (!window.confirm("确定从实验档案中删除这份媒体吗？")) return;
    await deleteExperimentMedia(activeChild.id, session.id, mediaId);
    await load();
    setMessage("媒体已从实验档案删除。");
  }, "媒体删除失败");

  const saveParentNote = () => run(async () => {
    setSession(await updateExperimentSession(activeChild.id, session.id, {
      parent_note: parentNote || null,
    }));
    setMessage("家长备注已保存，实验完成状态保持不变。");
  }, "家长备注保存失败");

  const finish = () => run(async () => {
    const completed = await completeExperiment(activeChild.id, session.id, parentNote);
    setSession(completed);
    setGrowth(await getExperimentGrowthCard(activeChild.id, session.id));
    setMessage("实验完成。只记录接触证据，没有自动产生认字答对记录。");
  }, "无法完成实验");

  const story = () => run(async () => {
    const result = await generateExperimentStory(activeChild.id, session.id);
    router.push(`/read/${result.version.id}`);
  }, "实验故事暂时无法生成");

  const askAI = () => run(async () => {
    const result = await generateExperimentAIParentTip(activeChild.id, session.id);
    setAiTip(result.parent_tip);
    setMessage("AI 建议已生成；它只是辅助内容，不会修改任何学习记录。");
  }, "AI 家长建议暂时不可用");

  return (
    <section className="science-session section-shell">
      <div className="reader-topbar">
        <Link href="/science">← 实验室</Link>
        <span>{session.status === "completed" ? "实验档案 · 已完成 ✓" : "进度自动保存"}</span>
      </div>
      <header>
        <p className="eyebrow">家庭陪伴实验 · {session.local_date}</p>
        <h1>{title}</h1>
        <p>{String(snapshot.guiding_question ?? "先听听孩子怎么想。")}</p>
      </header>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}

      {session.status === "completed" ? (
        <section className="experiment-archive-meta" aria-label="实验档案时间">
          <div><span>创建</span><strong>{formatTimestamp(session.created_at)}</strong></div>
          <div><span>完成</span><strong>{formatTimestamp(session.completed_at)}</strong></div>
          <div><span>最近更新</span><strong>{formatTimestamp(session.updated_at)}</strong></div>
        </section>
      ) : null}

      {session.status === "in_progress" ? (
        <>
          <nav className="experiment-steps" aria-label="实验步骤">
            {STEPS.map((item, index) => (
              <button className={session.current_step === item.key ? "active" : ""} disabled={working} key={item.key} onClick={() => void move(item.key)} type="button">
                <small>{index + 1}</small>{item.label}
              </button>
            ))}
          </nav>
          <div className="experiment-guidance">
            <article><p className="eyebrow">预期现象</p><p>{String(snapshot.expected_phenomenon ?? "")}</p></article>
            <article><p className="eyebrow">家长解释</p><p>{String(snapshot.parent_scientific_explanation ?? "")}</p></article>
          </div>
        </>
      ) : null}

      {editable ? (
        <section className="evidence-capture">
          <h2>{session.status === "completed" ? "实验现象与孩子回答" : "记录真实探索"}</h2>
          <p>{session.status === "completed" ? "档案完成后仍可补充和修正原记录；完成时间与完成状态不会改变。" : "保留孩子的原话与观察。标签只描述行为，不生成分数。"}</p>
          <div className="evidence-form">
            <select value={type} onChange={(event) => setType(event.target.value as ExperimentEvidence["evidence_type"])}>
              {EVIDENCE.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="尽量逐字记录孩子当时说的话…" />
            <button className="button button-primary" disabled={working || !text.trim()} onClick={() => void record()} type="button">添加记录</button>
          </div>
          <div className="evidence-list">
            {session.evidence.map((item) => (
              <article key={item.id}>
                <span>{EVIDENCE.find((row) => row.value === item.evidence_type)?.label ?? item.evidence_type}</span>
                {editingEvidenceId === item.id ? (
                  <div className="evidence-edit-row">
                    <textarea value={editingEvidenceText} onChange={(event) => setEditingEvidenceText(event.target.value)} />
                    <button disabled={working || !editingEvidenceText.trim()} onClick={() => void saveEvidence(item)} type="button">保存</button>
                    <button onClick={() => setEditingEvidenceId("")} type="button">取消</button>
                  </div>
                ) : (
                  <><p>{item.original_text}</p><button className="text-button" onClick={() => { setEditingEvidenceId(item.id); setEditingEvidenceText(item.original_text); }} type="button">修改</button></>
                )}
                <small>{item.capability_tags.join(" · ")}</small>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {editable ? (
        <section className="media-capture">
          <h2>{session.status === "completed" ? "实验照片与媒体档案" : "照片、视频或语音"}</h2>
          <p>媒体持久保存在家庭私有对象存储，只通过家庭鉴权入口读取；刷新或重新登录后仍可查看。</p>
          <label className="button button-secondary">添加媒体<input hidden type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/*" onChange={(event) => void upload(event.target.files?.[0])} /></label>
          <div className="experiment-media-grid">
            {session.media.map((item) => (
              <article className="experiment-media-item" key={item.id}>
                {item.media_kind === "image" ? <img alt={`实验记录 ${item.original_filename}`} src={`${getApiBaseUrl()}${item.content_url}`} /> : item.media_kind === "video" ? <video controls src={`${getApiBaseUrl()}${item.content_url}`} /> : <audio controls src={`${getApiBaseUrl()}${item.content_url}`} />}
                <small>{item.original_filename}</small>
                <div>
                  <label>替换<input hidden type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/*" onChange={(event) => void replace(item.id, event.target.files?.[0])} /></label>
                  <button disabled={working} onClick={() => void remove(item.id)} type="button">删除</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {family?.current_role === "admin" && editable ? (
        <section className="archive-parent-note">
          <label className="parent-note">家长备注<textarea value={parentNote} onChange={(event) => setParentNote(event.target.value)} /></label>
          <button className="button button-secondary" disabled={working} onClick={() => void saveParentNote()} type="button">保存家长备注</button>
        </section>
      ) : null}

      {session.status === "in_progress" ? (
        <button className="button button-primary experiment-finish" disabled={working} onClick={() => void finish()} type="button">完成实验并生成成长卡</button>
      ) : null}

      {session.status === "completed" && growth ? (
        <section className="growth-card">
          <p className="eyebrow">实验档案 · 科学成长记录</p>
          <h2>{growth.title}</h2>
          <p>陪伴者：{growth.accompanying_user}</p>
          <div className="growth-evidence-grid">
            <article><strong>预测</strong>{growth.prediction.map((line) => <p key={line}>{line}</p>)}</article>
            <article><strong>观察</strong>{growth.observation.map((line) => <p key={line}>{line}</p>)}</article>
            <article><strong>孩子原话</strong>{growth.child_original_words.map((line) => <p key={line}>{line}</p>)}</article>
            <article><strong>科学解释</strong><p>{growth.scientific_explanation}</p></article>
          </div>
          <p className="evidence-note">本记录不包含科学能力分数；完成实验仅产生一次知识接触证据。</p>
          {aiTip ? <aside className="ai-assistance"><strong>AI 家长讲解建议</strong><p>{aiTip}</p><small>辅助内容 · 不修改学习记录或掌握度</small></aside> : null}
          {family?.current_role === "admin" ? (
            <div className="inline-actions">
              <button className="button button-secondary" disabled={working} onClick={() => void askAI()} type="button">AI 生成家长讲解建议</button>
              <button className="button button-primary" disabled={working} onClick={() => void story()} type="button">用已学汉字生成实验故事</button>
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

export default function ExperimentSessionPage() {
  return <ProtectedPage><ExperimentRunner /></ProtectedPage>;
}
