"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import {
  mathAnswerStateClass,
  MathOptionVisual,
  MathProblemVisual,
  usesDirectVisualAnswers,
} from "@/components/math-problem-visual";
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
import {
  childFeedbackAudio,
  playCompletedFeedback,
  playCorrectFeedback,
  playIncorrectFeedback,
} from "@/lib/child-feedback-audio";
import { useResolvedChildExperienceMode } from "@/lib/experience-mode";

const STATE_LABELS: Record<MathState, string> = {
  unlearned: "未学习",
  introduced: "初步理解",
  practicing: "练习中",
  proficient: "能够独立完成",
  stable: "稳定掌握",
};

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

function MathDetailContent() {
  const params = useParams<{ knowledgePointId: string }>();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const resolvedChildMode = useResolvedChildExperienceMode();
  const childMode = resolvedChildMode === true;
  const [skill, setSkill] = useState<MathSkillDetail | null>(null);
  const [session, setSession] = useState<MathSession | null>(null);
  const [index, setIndex] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [hintUsed, setHintUsed] = useState(false);
  const [answered, setAnswered] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState<unknown>();
  const [correctAnswer, setCorrectAnswer] = useState<unknown>();
  const [journeyComplete, setJourneyComplete] = useState(false);
  const startedAt = useRef(0);
  const answerLocked = useRef(false);
  const flowGeneration = useRef(0);
  const autoStartedSkill = useRef<string | null>(null);

  const load = useCallback(async (expectedGeneration?: number) => {
    if (!activeChild) return;
    try {
      const value = await getMathSkillDetail(activeChild.id, params.knowledgePointId);
      if (
        expectedGeneration !== undefined &&
        expectedGeneration !== flowGeneration.current
      ) return;
      setSkill(value);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "数学学习页加载失败");
    }
  }, [activeChild, params.knowledgePointId]);

  useEffect(() => {
    flowGeneration.current += 1;
    autoStartedSkill.current = null;
    answerLocked.current = false;
    childFeedbackAudio.cancel();
    const generation = flowGeneration.current;
    const timer = window.setTimeout(() => {
      setSkill(null);
      setSession(null);
      setIndex(0);
      setMessage("");
      setSelectedAnswer(undefined);
      setCorrectAnswer(undefined);
      setJourneyComplete(false);
      void load(generation);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      flowGeneration.current += 1;
      childFeedbackAudio.cancel();
    };
  }, [load]);

  const begin = useCallback(async (mode: MathMode) => {
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
      setSelectedAnswer(undefined);
      setCorrectAnswer(undefined);
      answerLocked.current = false;
      startedAt.current = performance.now();
      window.setTimeout(
        () => childFeedbackAudio.speakInstruction(value.problems[0].render_payload.instruction),
        120,
      );
    } catch (reason) {
      autoStartedSkill.current = null;
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法开始练习");
    } finally {
      setWorking(false);
    }
  }, [activeChild, skill]);

  useEffect(() => {
    if (
      resolvedChildMode !== true ||
      !skill ||
      session ||
      journeyComplete ||
      autoStartedSkill.current === skill.knowledge_point_id
    ) return;
    autoStartedSkill.current = skill.knowledge_point_id;
    void begin("practice");
  }, [begin, journeyComplete, resolvedChildMode, session, skill]);

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

  const moveToProblem = (nextIndex: number, currentSession: MathSession) => {
    setIndex(nextIndex);
    setAnswered(false);
    setHintUsed(false);
    setMessage("");
    setSelectedAnswer(undefined);
    setCorrectAnswer(undefined);
    answerLocked.current = false;
    startedAt.current = performance.now();
    window.setTimeout(
      () => childFeedbackAudio.speakInstruction(
        currentSession.problems[nextIndex].render_payload.instruction,
      ),
      120,
    );
  };

  const completeChildSkill = async (generation: number) => {
    if (!skill) return;
    setMessage("完成啦！");
    await playCompletedFeedback();
    await wait(650);
    if (generation !== flowGeneration.current) return;
    if (skill.next) {
      const countValue = new URLSearchParams(window.location.search).get("count") || "3";
      router.replace(
        `/learn/math/${skill.next.knowledge_point_id}?source=continuous&count=${countValue}`,
      );
    } else {
      setJourneyComplete(true);
      setSession(null);
    }
  };

  const answer = async (value: unknown, answeredAt: number) => {
    if (!activeChild || !session || answered || answerLocked.current) return;
    answerLocked.current = true;
    childFeedbackAudio.cancel();
    const generation = ++flowGeneration.current;
    const problem = session.problems[index];
    setWorking(true);
    setSelectedAnswer(value);
    try {
      const result = await answerMathAttempt(activeChild.id, session.session_id, problem.attempt_id, {
        submittedAnswer: value,
        hintUsed,
        responseTimeMs: Math.max(0, Math.round(answeredAt - startedAt.current)),
      });
      setCorrectAnswer(result.correct_answer);
      if (childMode) {
        const correct = result.outcome === "correct";
        setMessage(correct ? "答对啦！" : "再看看哦。正确答案亮起来了。");
        setAnswered(true);
        setWorking(false);
        if (correct) await playCorrectFeedback();
        else await playIncorrectFeedback();
        await wait(correct ? 480 : 1050);
        if (generation !== flowGeneration.current) return;
        if (index + 1 >= session.problems.length) await completeChildSkill(generation);
        else moveToProblem(index + 1, session);
        return;
      }

      setMessage(result.feedback);
      const mayRetry = session.mode === "practice" && result.outcome === "incorrect";
      setAnswered(!mayRetry);
      if (mayRetry) {
        setHintUsed(true);
        answerLocked.current = false;
        childFeedbackAudio.speakInstruction(problem.render_payload.instruction);
      }
      if (result.session_completed) await load();
    } catch (reason) {
      answerLocked.current = false;
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
    moveToProblem(index + 1, session);
  };

  if (!skill || resolvedChildMode === null) return <main className="center-state section-shell">{error || "正在准备数学小任务…"}</main>;
  if (journeyComplete) return <main className="math-journey-complete section-shell"><span aria-hidden="true">🌟</span><h1>今天完成啦！</h1><p>你认真看、认真听，也勇敢地做完了。</p><Link className="button button-primary" href="/kids/today">回到今天</Link></main>;
  const problem = session?.problems[index];
  const directVisualAnswer = problem ? usesDirectVisualAnswers(problem.render_payload) : false;

  return <main className={`math-detail-page section-shell ${childMode ? "child-mode" : "parent-mode"} ${problem ? "has-problem" : "has-intro"}`}>
    {childMode ? <div className="math-child-context"><span>{skill.title}</span></div> : <div className="math-detail-topline"><button onClick={() => router.back()} type="button">← 返回数学学习路径</button><span>能力 {skill.position} / {skill.total}</span></div>}
    {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
    {!problem && childMode ? <section className="center-state compact math-auto-start"><span className="loading-spinner" aria-hidden="true" /><p>第一题马上来啦…</p></section> : null}
    {!problem && !childMode ? <section className="math-skill-intro">
      <div><p className="eyebrow">{skill.domain.replace("_", " ")}</p><h1>{skill.title}</h1><p>{skill.child_instruction}</p><span className={`math-state state-${skill.state_code}`}>{STATE_LABELS[skill.state_code]}</span></div>
      <div className="math-start-actions"><button disabled={working} onClick={() => void begin("practice")} type="button">开始 3 题练习</button><button className="secondary" disabled={working} onClick={() => void begin("assessment")} type="button">独立检查</button><button aria-label="朗读题目" className="listen" onClick={() => childFeedbackAudio.speakInstruction(skill.child_instruction)} type="button">🔊 听一听</button></div>
      <article className="math-offline-card"><p className="eyebrow">动手试一试</p><h2>{String(skill.settings.offline_instruction ?? skill.parent_tip)}</h2><div aria-label="记录动手活动" className="math-offline-observation"><button disabled={working} onClick={() => void observeOffline("correct")} type="button">独立完成</button><button disabled={working} onClick={() => void observeOffline("hinted_correct")} type="button">需要提示</button><button disabled={working} onClick={() => void observeOffline("uncertain")} type="button">暂时不会</button></div></article>
      <aside className="math-parent-detail"><h2>家长提示</h2><p>{skill.parent_tip}</p><h3>为什么系统这样判断</h3><ul>{skill.mastery_explanation.map((item) => <li key={item}>{item}</li>)}</ul><h3>常见困难与下一步</h3><ul>{skill.common_difficulties.map((item) => <li key={item}>{item}</li>)}</ul><p>当前策略：{skill.policy_key} · 表示方式：{skill.representation_types.join("、")}</p>{skill.prerequisites.length ? <p>建议先体验：{skill.prerequisites.map((item) => item.title).join("、")}（不硬锁）</p> : null}</aside>
      <nav aria-label="数学前后导航" className="math-sequence-nav">{skill.previous ? <Link href={`/learn/math/${skill.previous.knowledge_point_id}`}><span>← 上一个</span><strong>{skill.previous.title}</strong></Link> : <span />}{skill.next ? <Link href={`/learn/math/${skill.next.knowledge_point_id}`}><span>下一个 →</span><strong>{skill.next.title}</strong></Link> : <span>已到最后</span>}</nav>
    </section> : null}
    {problem ? <section className="math-problem-screen">
      <header><div>{!childMode ? <p className="eyebrow">数学 · {skill.title}</p> : null}<h1>第 {index + 1} / {session?.problems.length} 题</h1></div>{!childMode ? <span>{session?.mode === "assessment" ? "独立检查" : "练习"}</span> : null}</header>
      <p aria-live="polite" className={`math-feedback math-problem-feedback ${message ? "has-message" : ""}`} role="status">{message || " "}</p>
      <div className="math-main-task"><h2>{problem.render_payload.instruction}</h2><MathProblemVisual correctValue={correctAnswer} disabled={working || answered} onSelect={(value) => void answer(value, performance.now())} payload={problem.render_payload} revealCorrect={childMode && answered} selectedValue={selectedAnswer} /></div>
      {!directVisualAnswer ? <div className="math-answer-grid">{problem.render_payload.options.map((option, optionIndex) => <button aria-label={`答案 ${option.label}`} className={mathAnswerStateClass(option.value, { correctValue: correctAnswer, revealCorrect: childMode && answered, selectedValue: selectedAnswer })} disabled={working || answered} key={`${String(option.value)}-${optionIndex}`} onClick={() => void answer(option.value, performance.now())} type="button"><MathOptionVisual option={option} />{!childMode ? <small>{option.label}</small> : null}</button>)}</div> : null}
      <div className="math-problem-tools"><button aria-label="朗读题目" disabled={childMode && (working || answered)} onClick={() => childFeedbackAudio.speakInstruction(problem.render_payload.instruction)} type="button">🔊 再听一次</button>{session?.mode === "practice" && !childMode ? <button onClick={() => { setHintUsed(true); setMessage("可以一个个指着数，或者用手里的积木摆一摆。"); }} type="button">给我一点提示</button> : null}{answered && !childMode ? <button className="primary" onClick={next} type="button">{index + 1 === session?.problems.length ? "完成" : "下一题 →"}</button> : null}</div>
    </section> : null}
  </main>;
}

export default function MathSkillPage() {
  return <ProtectedPage><MathDetailContent /></ProtectedPage>;
}
