"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  getPinyinItemDetail,
  recordPinyinAssessment,
  recordPinyinLearning,
  type AssessmentOutcome,
  type PinyinItemDetail,
  type PinyinState,
} from "@/lib/api/client";
import { playPinyinAudio } from "@/lib/pinyin-audio";
import { useChildExperienceMode } from "@/lib/experience-mode";

const STATE_LABELS: Record<PinyinState, string> = {
  unlearned: "未学习",
  introduced: "初识",
  practicing: "练习中",
  proficient: "基本掌握",
  stable: "稳定掌握",
};

const KIND_LABELS = { initial: "声母", final: "韵母", tone: "声调", whole: "整体认读" } as const;

function PinyinDetailContent() {
  const params = useParams<{ knowledgePointId: string }>();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [item, setItem] = useState<PinyinItemDetail | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [listeningOpen, setListeningOpen] = useState(false);
  const startedAt = useRef(0);

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setItem(await getPinyinItemDetail(activeChild.id, params.knowledgePointId));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "拼音学习页加载失败");
    }
  }, [activeChild, params.knowledgePointId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setItem(null);
      setListeningOpen(false);
      setMessage("");
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const play = async () => {
    if (!item) return;
    setError("");
    try {
      const played = await playPinyinAudio(item);
      if (!played) setError("这个拼音暂时没有可用声音，请让家长示范。 ");
    } catch {
      setError("声音暂时没有播放出来，可以再试一次。");
    }
  };

  const completeLearning = async () => {
    if (!activeChild || !item) return;
    setWorking(true);
    try {
      await recordPinyinLearning(
        activeChild.id,
        item.knowledge_point_id,
        item.learned ? "reviewed" : "introduced",
      );
      setMessage(item.learned ? "这次复习已经记入学习记录。" : "第一次正式学习已经记录。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法保存学习记录");
    } finally {
      setWorking(false);
    }
  };

  const observe = async (
    dimension: "recognition" | "pronunciation",
    outcome: AssessmentOutcome,
  ) => {
    if (!activeChild || !item) return;
    setWorking(true);
    try {
      await recordPinyinAssessment(activeChild.id, {
        knowledgePointId: item.knowledge_point_id,
        outcome,
        dimension,
        assessmentKind: dimension === "pronunciation" ? "oral_check" : "recognition",
        metadata: { source: "adult_observation" },
      });
      setMessage("家长观察已保存；这是成人观察，不是自动发音评分。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "暂时无法保存观察");
    } finally {
      setWorking(false);
    }
  };

  const startListening = async (startedAtMs: number) => {
    startedAt.current = startedAtMs;
    setListeningOpen(true);
    setMessage("");
    await play();
  };

  const answerListening = async (answerId: string, answeredAtMs: number) => {
    if (!activeChild || !item) return;
    const correct = answerId === item.knowledge_point_id;
    const responseTimeMs = Math.max(0, Math.round(answeredAtMs - startedAt.current));
    setWorking(true);
    try {
      const dimension = item.kind === "tone" ? "tone" : "listening";
      await recordPinyinAssessment(activeChild.id, {
        knowledgePointId: item.knowledge_point_id,
        outcome: correct ? "correct" : "incorrect",
        dimension,
        assessmentKind: "listening_check",
        responseTimeMs,
        metadata: { selected_knowledge_point_id: answerId },
      });
      if (correct && item.kind === "tone") {
        await recordPinyinAssessment(activeChild.id, {
          knowledgePointId: item.knowledge_point_id,
          outcome: "correct",
          dimension: "listening",
          assessmentKind: "listening_check",
          responseTimeMs,
          metadata: { paired_tone_listening_evidence: true },
        });
      }
      setMessage(correct ? "听出来啦！还可以再听一次。" : "再听一次试试看，慢慢分辨就好。");
      await load();
      if (!correct) await play();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "听音练习暂时无法保存");
    } finally {
      setWorking(false);
    }
  };

  if (!item) {
    return <main className="center-state section-shell">{error || "正在准备声音和大拼音卡…"}</main>;
  }

  const gesture = typeof item.metadata.gesture === "string" ? item.metadata.gesture : null;
  const shape = typeof item.metadata.shape === "string" ? item.metadata.shape : null;

  return (
    <main className="pinyin-detail-page section-shell">
      <div className="pinyin-detail-topline">
        <button onClick={() => router.back()} type="button">← 返回拼音学习路径</button>
        <span>第 {item.position} / {item.total}</span>
      </div>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}
      <section className="pinyin-learning-stage">
        <aside className="pinyin-focus-panel">
          <p>{KIND_LABELS[item.kind]}</p>
          <h1>{item.display_text}</h1>
          {gesture ? <div className="pinyin-tone-gesture"><strong>{gesture}</strong><span>{shape}</span></div> : null}
          {item.kind === "whole" ? <strong className="whole-reading-note">整体认读 · 直接读出来</strong> : null}
          <button aria-label={`播放 ${item.display_text} 的发音`} className="pinyin-main-audio" onClick={() => void play()} type="button"><span aria-hidden="true">🔊</span> 听一听</button>
          <button aria-label={`重新播放 ${item.display_text} 的发音`} className="pinyin-repeat-audio" onClick={() => void play()} type="button">👂 再听一次</button>
          <span className={`pinyin-state state-${item.state_code}`}>{STATE_LABELS[item.state_code]}</span>
          <nav aria-label="拼音前后导航" className="pinyin-sequence-nav">
            {item.previous ? <Link href={`/learn/pinyin/${item.previous.knowledge_point_id}?source=path`}><span>← 上一个</span><strong>{item.previous.display_text}</strong></Link> : <span aria-disabled="true">← 上一个</span>}
            {item.next ? <Link href={`/learn/pinyin/${item.next.knowledge_point_id}?source=path`}><span>下一个 →</span><strong>{item.next.display_text}</strong></Link> : <span aria-disabled="true">已到最后</span>}
          </nav>
        </aside>

        <div className="pinyin-learning-content">
          <article><p className="eyebrow">听一听</p><h2>{item.pronunciation_cue || "请家长示范这个中文拼音声音。"}</h2><button aria-label={`播放 ${item.display_text} 的中文示范`} onClick={() => void play()} type="button">🔊 播放中文示范</button></article>
          <article><p className="eyebrow">例子</p><h2>{item.example_text || "听完后跟着读一读"}</h2>{item.example_pinyin ? <p className="pinyin-example-text">{item.example_pinyin}</p> : null}</article>
          <article><p className="eyebrow">小提示</p><p>{item.description}</p></article>
          <article className="parent-learning-tip"><p className="eyebrow">家长提示</p><p>{item.parent_tip}</p>{item.confusing.length ? <div className="pinyin-confusions"><span>容易混淆：</span>{item.confusing.map((value) => <Link href={`/learn/pinyin/${value.knowledge_point_id}`} key={value.knowledge_point_id}>{value.display_text}</Link>)}</div> : null}</article>
        </div>
      </section>

      <section className="pinyin-action-panel">
        <div><h2>跟我读</h2><p>播放声音后让孩子自然模仿。系统不会自动给儿童发音打分。</p><button className="button button-primary" onClick={() => void play()} type="button">🗣 跟我读</button><button className="button button-secondary" disabled={working} onClick={() => void completeLearning()} type="button">{item.learned ? "完成这次复习" : "完成这次学习"}</button></div>
        {!childMode ? <div><h3>家长观察 · 认出符号</h3><div className="pinyin-observation-buttons"><button disabled={working} onClick={() => void observe("recognition", "correct")} type="button">认出来了</button><button disabled={working} onClick={() => void observe("recognition", "hinted_correct")} type="button">需要提示</button><button disabled={working} onClick={() => void observe("recognition", "uncertain")} type="button">还不熟</button></div></div> : null}
        {!childMode ? <div><h3>家长观察 · 跟读</h3><div className="pinyin-observation-buttons"><button disabled={working} onClick={() => void observe("pronunciation", "correct")} type="button">孩子能跟读</button><button disabled={working} onClick={() => void observe("pronunciation", "hinted_correct")} type="button">需要提示</button><button disabled={working} onClick={() => void observe("pronunciation", "uncertain")} type="button">暂时不会</button></div></div> : null}
      </section>

      <section className="pinyin-listening-task">
        <header><div><p className="eyebrow">听音选择</p><h2>听一听，哪个是刚才的声音？</h2></div><button aria-label={`重新播放 ${item.display_text} 的发音`} onClick={(event) => void startListening(event.timeStamp)} type="button">🔊 {listeningOpen ? "重新播放" : "开始听音"}</button></header>
        {listeningOpen ? <div className="pinyin-listening-options">{item.listening_options.map((option) => <button disabled={working} key={option.knowledge_point_id} onClick={(event) => void answerListening(option.knowledge_point_id, event.timeStamp)} type="button">{option.display_text}</button>)}</div> : <p>选项很少，可以反复听；没有扣分，也不会出现羞辱性的红叉。</p>}
      </section>
      <p className="pinyin-policy-note">掌握策略：{item.policy_key} · 听音、认读、声调、拼读与跟读观察分别保存；同一天重复点击不能直接变成稳定掌握。</p>
    </main>
  );
}

export default function PinyinDetailPage() {
  return <ProtectedPage><PinyinDetailContent /></ProtectedPage>;
}
