"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  getPinyinItemDetail,
  getPinyinPractices,
  recordPinyinAssessment,
  type AssessmentOutcome,
  type PinyinItemDetail,
  type PinyinPractice,
} from "@/lib/api/client";
import { playPinyinAudio } from "@/lib/pinyin-audio";
import { useChildExperienceMode } from "@/lib/experience-mode";
import { speakChinese } from "@/lib/speech";

function PinyinBlendingContent() {
  const { activeChild } = useActiveChild();
  const childMode = useChildExperienceMode();
  const [practices, setPractices] = useState<PinyinPractice[]>([]);
  const [index, setIndex] = useState(0);
  const [initial, setInitial] = useState<PinyinItemDetail | null>(null);
  const [finalItem, setFinalItem] = useState<PinyinItemDetail | null>(null);
  const [animating, setAnimating] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const practice = practices[index] ?? null;

  const loadPracticeDetails = useCallback(async (value: PinyinPractice) => {
    if (!activeChild) return;
    const [initialValue, finalValue] = await Promise.all([
      getPinyinItemDetail(activeChild.id, value.initial_knowledge_point_id),
      getPinyinItemDetail(activeChild.id, value.final_knowledge_point_id),
    ]);
    setInitial(initialValue);
    setFinalItem(finalValue);
  }, [activeChild]);

  useEffect(() => {
    if (!activeChild) return;
    const timer = window.setTimeout(() => {
      void getPinyinPractices().then((page) => {
        setPractices(page.items);
        if (page.items[0]) void loadPracticeDetails(page.items[0]);
      }).catch((reason) => setError(reason instanceof ApiClientError ? reason.message : "拼读练习加载失败"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeChild, loadPracticeDetails]);

  const move = (nextIndex: number) => {
    const next = practices[nextIndex];
    if (!next) return;
    setIndex(nextIndex);
    setInitial(null);
    setFinalItem(null);
    setMessage("");
    void loadPracticeDetails(next);
  };

  const blend = () => {
    if (!practice || !initial || !finalItem) return;
    setAnimating(true);
    setMessage("先听声母，再听韵母，最后连起来。");
    void playPinyinAudio(initial);
    window.setTimeout(() => void playPinyinAudio(finalItem), 1400);
    window.setTimeout(() => speakChinese(practice.pronunciation_cue), 2800);
    window.setTimeout(() => setAnimating(false), 4200);
  };

  const observe = async (outcome: AssessmentOutcome) => {
    if (!activeChild || !practice) return;
    setWorking(true);
    try {
      await recordPinyinAssessment(activeChild.id, {
        knowledgePointId: practice.final_knowledge_point_id,
        outcome,
        dimension: "blending",
        assessmentKind: "practice_check",
        metadata: {
          practice_key: practice.practice_key,
          initial: practice.initial,
          underlying_final: practice.underlying_final,
          display_syllable: practice.display_syllable,
          adult_observation: true,
        },
      });
      setMessage(outcome === "correct" ? "这次独立拼读已经记录。" : outcome === "hinted_correct" ? "已记录为需要提示。" : "先休息一下，下次再试也很好。");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "拼读观察暂时无法保存");
    } finally {
      setWorking(false);
    }
  };

  if (!practice || !initial || !finalItem) {
    return <main className="center-state section-shell">{error || "正在准备拼读声音…"}</main>;
  }

  return (
    <main className="pinyin-blending-page section-shell">
      <header><div><Link href="/learn/pinyin">← 返回拼音学习</Link><p className="eyebrow">拼读练习</p><h1>把两个声音连起来</h1></div><span>{index + 1} / {practices.length}</span></header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}
      <section className={`pinyin-blend-stage ${animating ? "is-blending" : ""}`}>
        <button aria-label={`播放声母 ${practice.initial} 的发音`} onClick={() => void playPinyinAudio(initial)} type="button"><strong>{practice.initial}</strong><span>🔊 听声母</span></button>
        <span className="pinyin-blend-plus">+</span>
        <button aria-label={`播放韵母 ${practice.display_final} 的发音`} onClick={() => void playPinyinAudio(finalItem)} type="button"><strong>{practice.display_final}</strong><span>🔊 听韵母</span></button>
        <div className="pinyin-blend-lines" aria-hidden="true"><i /><i /></div>
        <button aria-label={`播放音节 ${practice.display_syllable} 的中文示范`} className="pinyin-blend-result" onClick={() => speakChinese(practice.pronunciation_cue)} type="button"><strong>{practice.display_syllable}</strong><span>🔊 {practice.pronunciation_cue}</span></button>
      </section>
      {practice.metadata.umlaut_omitted ? <aside className="pinyin-umlaut-note"><strong>ü 的小规则</strong><p>{practice.initial} 和 ü 相拼时，显示为 {practice.display_syllable}，但系统仍然保留 underlying final = ü，不会丢失规则。</p></aside> : null}
      <div className="pinyin-blend-actions"><button className="button button-primary" onClick={blend} type="button">拼一拼</button><small>播放只是练习，不会自动写成“答对”。</small></div>
      {!childMode ? <section className="pinyin-blend-observation"><h2>家长观察</h2><p>孩子真正尝试以后再选择；没有自动语音评分。</p><div><button disabled={working} onClick={() => void observe("correct")} type="button">能独立拼出</button><button disabled={working} onClick={() => void observe("hinted_correct")} type="button">需要提示</button><button disabled={working} onClick={() => void observe("uncertain")} type="button">还不熟</button></div></section> : null}
      <nav aria-label="拼读练习前后导航" className="pinyin-blend-nav"><button disabled={index === 0} onClick={() => move(index - 1)} type="button">← 上一个</button><button disabled={index >= practices.length - 1} onClick={() => move(index + 1)} type="button">下一个 →</button></nav>
    </main>
  );
}

export default function PinyinBlendingPage() {
  return <ProtectedPage><PinyinBlendingContent /></ProtectedPage>;
}
