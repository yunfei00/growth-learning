"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { MathOptionVisual, MathProblemVisual } from "@/components/math-problem-visual";
import { ProtectedPage } from "@/components/protected-page";
import {
  answerMathAttempt,
  ApiClientError,
  getMathSkillDetail,
  recordMathOfflineObservation,
  startMathSession,
  type MathMode,
  type MathSession,
  type MathSkillDetail,
  type MathState,
} from "@/lib/api/client";
import { useChildExperienceMode } from "@/lib/experience-mode";

const STATE_LABELS: Record<MathState, string> = {
  unlearned: "未学习",
  introduced: "初步理解",
  practicing: "练习中",
  proficient: "能够独立完成",
  stable: "稳定掌握",
};

function speakInstruction(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 0.82;
  window.speechSynthesis.speak(utterance);
  return true;
}

function MathDetailContent() {
  const params = useParams<{ knowledgePointId: string }>();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [skill, setSkill] = useState<MathSkillDetail | null>(null);
  const [session, setSession] = useState<MathSession | null>(null);
  const [index, setIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [hintUsed, setHintUsed] = useState(false);
  const [answered, setAnswered] = useState(false);
  const startedAt = useRef(0);

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setSkill(await getMathSkillDetail(activeChild.id, params.knowledgePointId));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "数学学习页加载失败");
    }
  }, [activeChild, params.knowledgePointId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { setSession(null); setIndex(0); void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const begin = async (mode: MathMode) => {
    if (!activeChild || !skill) return;
    setWorking(true);
    try {
      const countValue = new URLSearchParams(window.location.search).get("count");
      const count = Math.min(5, Math.max(3, Number(countValue) || 3));
      const value = await startMathSession(activeChild.id, {
        knowledgePointId: skill.knowledge_point_id,
        mode,
        problemCount: count,
        dimension: mode === "assessment" ? "independent" : "understanding",
      });
      setSession(value);
      setIndex(0);
      setAnswered(false);
      setHintUsed(false);
      setMessage("");
      startedAt.current = performance.now();
      speakInstruction(value.problems[0].render_payload.instruction);
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法开始练习");
    } finally {
      setWorking(false);
    }
  };

  const observeOffline = async (outcome: "correct" | "hinted_correct" | "uncertain") => {
    if (!activeChild || !skill) return;
    setWorking(true);
    try {
      await recordMathOfflineObservation(activeChild.id, skill.knowledge_point_id, outcome);
      setMessage("动手活动已经记录，会由 math-v1 与其他证据一起判断。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法记录动手活动");
    } finally {
      setWorking(false);
    }
  };

  const answer = async (value: unknown, answeredAt: number) => {
    if (!activeChild || !session || answered) return;
    const problem = session.problems[index];
    setWorking(true);
    try {
      const result = await answerMathAttempt(activeChild.id, session.session_id, problem.attempt_id, {
        submittedAnswer: value,
        hintUsed,
        responseTimeMs: Math.max(0, Math.round(answeredAt - startedAt.current)),
      });
      setMessage(result.feedback);
      const mayRetry = session.mode === "practice" && result.outcome === "incorrect";
      setAnswered(!mayRetry);
      if (mayRetry) {
        setHintUsed(true);
        speakInstruction(problem.render_payload.instruction);
      }
      if (result.session_completed) await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法保存这次回答");
    } finally {
      setWorking(false);
    }
  };

  const next = () => {
    if (!session) return;
    if (index + 1 >= session.problems.length) {
      setSession(null);
      setMessage("这一小组完成啦！可以再练一次，或返回数学路径。");
      return;
    }
    const nextIndex = index + 1;
    setIndex(nextIndex);
    setAnswered(false);
    setHintUsed(false);
    setMessage("");
    startedAt.current = performance.now();
    speakInstruction(session.problems[nextIndex].render_payload.instruction);
  };

  if (!skill) return <main className="center-state section-shell">{error || "正在准备数学小任务…"}</main>;
  const problem = session?.problems[index];

  return <main className="math-detail-page section-shell">
    <div className="math-detail-topline"><button onClick={() => router.back()} type="button">← 返回数学学习路径</button><span>能力 {skill.position} / {skill.total}</span></div>
    {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
    {message ? <p className="math-feedback" role="status">{message}</p> : null}
    {!problem ? <section className="math-skill-intro">
      <div><p className="eyebrow">{skill.domain.replace("_", " ")}</p><h1>{skill.title}</h1><p>{skill.child_instruction}</p><span className={`math-state state-${skill.state_code}`}>{STATE_LABELS[skill.state_code]}</span></div>
      <div className="math-start-actions"><button disabled={working} onClick={() => void begin("practice")} type="button">开始 3 题练习</button>{!childMode ? <button className="secondary" disabled={working} onClick={() => void begin("assessment")} type="button">独立检查</button> : null}<button aria-label="朗读题目" className="listen" onClick={() => speakInstruction(skill.child_instruction)} type="button">🔊 听一听</button></div>
      <article className="math-offline-card"><p className="eyebrow">动手试一试</p><h2>{String(skill.settings.offline_instruction ?? skill.parent_tip)}</h2>{!childMode ? <div aria-label="记录动手活动" className="math-offline-observation"><button disabled={working} onClick={() => void observeOffline("correct")} type="button">独立完成</button><button disabled={working} onClick={() => void observeOffline("hinted_correct")} type="button">需要提示</button><button disabled={working} onClick={() => void observeOffline("uncertain")} type="button">暂时不会</button></div> : null}</article>
      {!childMode ? <aside className="math-parent-detail"><h2>家长提示</h2><p>{skill.parent_tip}</p><h3>为什么系统这样判断</h3><ul>{skill.mastery_explanation.map((item) => <li key={item}>{item}</li>)}</ul><h3>常见困难与下一步</h3><ul>{skill.common_difficulties.map((item) => <li key={item}>{item}</li>)}</ul><p>当前策略：{skill.policy_key} · 表示方式：{skill.representation_types.join("、")}</p>{skill.prerequisites.length ? <p>建议先体验：{skill.prerequisites.map((item) => item.title).join("、")}（不硬锁）</p> : null}</aside> : null}
      <nav aria-label="数学前后导航" className="math-sequence-nav">{skill.previous ? <Link href={`/learn/math/${skill.previous.knowledge_point_id}`}><span>← 上一个</span><strong>{skill.previous.title}</strong></Link> : <span />}{skill.next ? <Link href={`/learn/math/${skill.next.knowledge_point_id}`}><span>下一个 →</span><strong>{skill.next.title}</strong></Link> : <span>已到最后</span>}</nav>
    </section> : <section className="math-problem-screen">
      <header><div><p className="eyebrow">数学 · {skill.title}</p><h1>第 {index + 1} / {session?.problems.length} 题</h1></div><span>{session?.mode === "assessment" ? "独立检查" : "练习"}</span></header>
      <div className="math-main-task"><MathProblemVisual payload={problem.render_payload} /><h2>{problem.render_payload.instruction}</h2></div>
      <div className="math-answer-grid">{problem.render_payload.options.map((option, optionIndex) => <button aria-label={`答案 ${option.label}`} disabled={working || answered} key={`${String(option.value)}-${optionIndex}`} onClick={() => void answer(option.value, performance.now())} type="button"><MathOptionVisual option={option} /></button>)}</div>
      <div className="math-problem-tools"><button aria-label="朗读题目" onClick={() => speakInstruction(problem.render_payload.instruction)} type="button">🔊 再听一次</button>{session?.mode === "practice" ? <button onClick={() => { setHintUsed(true); setMessage("可以一个个指着数，或者用手里的积木摆一摆。"); }} type="button">给我一点提示</button> : null}{answered ? <button className="primary" onClick={next} type="button">{index + 1 === session?.problems.length ? "完成" : "下一题 →"}</button> : null}</div>
    </section>}
  </main>;
}

export default function MathSkillPage() {
  return <ProtectedPage><MathDetailContent /></ProtectedPage>;
}
