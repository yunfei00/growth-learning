"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { EnglishVisualCard } from "@/components/english-visual";
import { ProtectedPage } from "@/components/protected-page";
import {
  answerEnglishAttempt,
  ApiClientError,
  getEnglishItemDetail,
  recordEnglishSpeakingObservation,
  startEnglishSession,
  type EnglishAudio,
  type EnglishDimension,
  type EnglishItemDetail,
  type EnglishMode,
  type EnglishSession,
  type EnglishState,
} from "@/lib/api/client";
import { playEnglishAudio } from "@/lib/english-playback";
import { useChildExperienceMode } from "@/lib/experience-mode";

const STATE_LABELS: Record<EnglishState, string> = {
  unlearned: "未学习",
  introduced: "初次接触",
  practicing: "练习中",
  proficient: "基本掌握",
  stable: "稳定掌握",
};

function EnglishDetailContent() {
  const params = useParams<{ knowledgePointId: string }>();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [item, setItem] = useState<EnglishItemDetail | null>(null);
  const [session, setSession] = useState<EnglishSession | null>(null);
  const [index, setIndex] = useState(0);
  const [answered, setAnswered] = useState(false);
  const [hintUsed, setHintUsed] = useState(false);
  const [audioReplays, setAudioReplays] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const startedAt = useRef(0);

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setItem(await getEnglishItemDetail(activeChild.id, params.knowledgePointId));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "英语学习页加载失败");
    }
  }, [activeChild, params.knowledgePointId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { setSession(null); setIndex(0); void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const play = (audio: EnglishAudio | undefined, countReplay = true) => {
    if (!audio) return;
    if (playEnglishAudio(audio) && countReplay) setAudioReplays((value) => value + 1);
    if (!audio.available) setMessage(audio.instruction_zh);
  };

  const begin = async (mode: EnglishMode, dimension?: EnglishDimension) => {
    if (!activeChild || !item) return;
    setWorking(true);
    try {
      const countValue = new URLSearchParams(window.location.search).get("count");
      const count = Math.min(5, Math.max(1, Number(countValue) || 3));
      const value = await startEnglishSession(activeChild.id, {
        knowledgePointId: item.knowledge_point_id,
        mode,
        exerciseCount: count,
        dimension,
      });
      setSession(value);
      setIndex(0);
      setAnswered(false);
      setHintUsed(false);
      setAudioReplays(0);
      setMessage("");
      startedAt.current = performance.now();
      const firstAudio = value.problems[0].prompt.audio;
      window.setTimeout(() => play(firstAudio, false), 150);
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法开始英语练习");
    } finally {
      setWorking(false);
    }
  };

  const answer = async (value: unknown, answeredAt: number) => {
    if (!activeChild || !session || answered) return;
    const problem = session.problems[index];
    setWorking(true);
    try {
      const result = await answerEnglishAttempt(
        activeChild.id,
        session.session_id,
        problem.attempt_id,
        {
          submittedAnswer: value,
          hintUsed,
          audioReplays,
          responseTimeMs: Math.max(0, Math.round(answeredAt - startedAt.current)),
        },
      );
      setMessage(result.feedback);
      const mayRetry = session.mode === "practice" && result.outcome === "incorrect";
      setAnswered(!mayRetry);
      setAudioReplays(0);
      if (mayRetry) {
        setHintUsed(true);
        play(problem.prompt.audio, false);
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
      setMessage("这一小组完成啦！可以再听一次，或返回英语声音乐园。");
      return;
    }
    const nextIndex = index + 1;
    setIndex(nextIndex);
    setAnswered(false);
    setHintUsed(false);
    setAudioReplays(0);
    setMessage("");
    startedAt.current = performance.now();
    window.setTimeout(() => play(session.problems[nextIndex].prompt.audio, false), 120);
  };

  const observeSpeaking = async (observation: "willing_to_repeat" | "can_say" | "needs_prompt" | "not_yet") => {
    if (!activeChild || !item) return;
    setWorking(true);
    try {
      await recordEnglishSpeakingObservation(activeChild.id, item.knowledge_point_id, observation);
      setMessage("口语表现已按家长观察保存，不使用自动语音评分。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法记录口语表现");
    } finally {
      setWorking(false);
    }
  };

  if (!item) return <main className="center-state section-shell">{error || "正在准备声音和图片…"}</main>;
  const problem = session?.problems[index];
  const assessmentDimensions: Array<{ dimension: EnglishDimension; label: string }> =
    item.kind === "word" || item.kind === "phrase"
      ? [
          { dimension: "listening", label: "听力检查" },
          { dimension: "meaning", label: "理解检查" },
        ]
      : item.kind === "letter"
        ? [
            { dimension: "letter_name", label: "字母名称检查" },
            { dimension: "case_matching", label: "大小写配对检查" },
          ]
        : [
            {
              dimension: item.category === "cvc" ? "decoding" : "sound_recognition",
              label: item.category === "cvc" ? "拼读检查" : "辨音检查",
            },
          ];

  return <main className="english-detail-page section-shell">
    <div className="english-detail-topline"><button onClick={() => router.back()} type="button">← 返回英语声音乐园</button><span>{item.position} / {item.total}</span></div>
    {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
    {message ? <p className="english-feedback" role="status">{message}</p> : null}
    {!problem ? <section className="english-item-intro">
      <div className="english-item-stage"><EnglishVisualCard label={item.meaning_zh} visual={item.visual} /><div><p className="eyebrow">{item.category_label}</p><h1>{item.text}</h1><p className="english-meaning">{item.meaning_zh}</p>{item.kind === "letter" ? <p className="english-letter-pair">{String(item.metadata.uppercase ?? item.text)} · {String(item.metadata.lowercase ?? item.text.toLowerCase())}</p> : null}{item.kind === "phonics" && Array.isArray(item.metadata.segments) ? <p className="english-segments">{item.metadata.segments.map(String).join(" · ")}</p> : null}<span className={`english-state state-${item.state_code}`}>{STATE_LABELS[item.state_code]}</span></div></div>
      <div className="english-start-actions"><button className="listen" disabled={!item.audio.available} onClick={() => play(item.audio)} type="button">🔊 听一听</button><button disabled={working} onClick={() => void begin("practice")} type="button">开始声音练习</button>{!childMode ? assessmentDimensions.map((value) => <button className="secondary" disabled={working} key={value.dimension} onClick={() => void begin("assessment", value.dimension)} type="button">{value.label}</button>) : null}</div>
      {item.example_text ? <article className="english-example-card"><p className="eyebrow">放进小场景</p><strong>{item.example_text}</strong><span>{item.example_meaning_zh}</span></article> : null}
      {!childMode && ["word", "phrase"].includes(item.kind) ? <article className="english-speaking-card"><h2>家长观察：孩子愿意说吗？</h2><p>只记录自然表现，不做自动发音评分，也不要求标准口音。</p><div><button disabled={working} onClick={() => void observeSpeaking("can_say")} type="button">能自然说</button><button disabled={working} onClick={() => void observeSpeaking("willing_to_repeat")} type="button">愿意跟读</button><button disabled={working} onClick={() => void observeSpeaking("needs_prompt")} type="button">需要提示</button><button disabled={working} onClick={() => void observeSpeaking("not_yet")} type="button">暂时不说</button></div></article> : null}
      {!childMode ? <aside className="english-parent-detail"><h2>家长提示</h2><p>{item.parent_tip}</p><h3>系统怎样判断</h3><ul>{item.mastery_explanation.map((value) => <li key={value}>{value}</li>)}</ul><p>当前策略：{item.policy_key} · 音频：{item.audio.strategy} · {item.audio.accent}</p><small>视觉来源：{item.visual.source} · {item.visual.license}</small></aside> : null}
      <nav aria-label="英语前后导航" className="english-sequence-nav">{item.previous ? <Link href={`/learn/english/${item.previous.knowledge_point_id}`}><span>← 上一个</span><strong>{item.previous.text}</strong></Link> : <span />}{item.next ? <Link href={`/learn/english/${item.next.knowledge_point_id}`}><span>下一个 →</span><strong>{item.next.text}</strong></Link> : <span>已到最后</span>}</nav>
    </section> : <section className="english-problem-screen">
      <header><div><p className="eyebrow">English · {item.category_label}</p><h1>第 {index + 1} / {session?.problems.length} 题</h1></div><span>{session?.mode === "assessment" ? "独立检查" : "声音练习"}</span></header>
      <div className="english-main-task">{problem.prompt.visual ? <EnglishVisualCard label="题目图片" visual={problem.prompt.visual} /> : null}{problem.prompt.text ? <strong className="english-prompt-text">{problem.prompt.text}</strong> : null}{problem.prompt.segments ? <strong className="english-prompt-segments">{problem.prompt.segments.join(" · ")}</strong> : null}<h2>{String(problem.prompt.instruction ?? "听一听，选一个答案")}</h2>{problem.prompt.audio ? <button aria-label="播放题目声音" className="english-big-audio" onClick={() => play(problem.prompt.audio)} type="button">🔊</button> : null}</div>
      <div className="english-answer-grid">{problem.options.map((option) => option.audio ? <article className="english-audio-option" key={String(option.value)}><button aria-label={`播放${option.assessment_alt}`} disabled={working || answered} onClick={() => play(option.audio)} type="button">🔊<small>{option.assessment_alt}</small></button><button disabled={working || answered} onClick={() => void answer(option.value, performance.now())} type="button">选这个声音</button></article> : <button aria-label={option.assessment_alt} disabled={working || answered} key={String(option.value)} onClick={() => void answer(option.value, performance.now())} type="button">{option.visual ? <EnglishVisualCard label={option.assessment_alt} visual={option.visual} /> : null}{option.text ? <strong>{option.text}</strong> : null}<small>{option.assessment_alt}</small></button>)}</div>
      <div className="english-problem-tools">{problem.prompt.audio ? <button onClick={() => play(problem.prompt.audio)} type="button">🔊 再听一次</button> : null}{session?.mode === "practice" ? <button onClick={() => { setHintUsed(true); setMessage(item.meaning_zh); }} type="button">给我中文提示</button> : null}{answered ? <button className="primary" onClick={next} type="button">{index + 1 === session?.problems.length ? "完成" : "下一题 →"}</button> : null}</div>
    </section>}
  </main>;
}

export default function EnglishItemPage() {
  return <ProtectedPage><EnglishDetailContent /></ProtectedPage>;
}
