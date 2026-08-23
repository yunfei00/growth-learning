"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type CharacterAIAssistance,
  type CharacterMasteryDetail,
  generateCharacterAIAssistance,
  getCharacterMasteryDetail,
} from "@/lib/api/client";

const LEVEL_LABELS = {
  unlearned: "未学习",
  introduced: "初识",
  recognizing: "基本认识",
  proficient: "熟练",
  stable: "稳定掌握",
} as const;

function CharacterDetailContent() {
  const params = useParams<{ knowledgePointId: string }>();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const [detail, setDetail] = useState<CharacterMasteryDetail | null>(null);
  const [ai, setAI] = useState<CharacterAIAssistance | null>(null);
  const [practiceOpen, setPracticeOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setDetail(await getCharacterMasteryDetail(activeChild.id, params.knowledgePointId));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "汉字详情加载失败");
    }
  }, [activeChild, params.knowledgePointId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const speak = () => {
    if (!detail || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(detail.state.character);
    utterance.lang = "zh-CN";
    utterance.rate = 0.75;
    window.speechSynthesis.speak(utterance);
  };

  const askAI = async () => {
    if (!activeChild) return;
    setWorking(true);
    setError("");
    try {
      setAI(await generateCharacterAIAssistance(activeChild.id, params.knowledgePointId));
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "AI 讲解暂时不可用");
    } finally {
      setWorking(false);
    }
  };

  if (!detail) {
    return <main className="center-state section-shell">{error || "正在打开汉字学习页…"}</main>;
  }
  const character = detail.state;
  const words = ai?.words ?? character.common_words;
  const explanation = ai?.simple_explanation ?? character.simple_meaning;
  const sentence = ai?.example_sentence ?? character.example_sentence;
  const parentTip = ai?.parent_tip ?? character.parent_tip;

  return (
    <main className="character-detail-page section-shell">
      <button className="character-back" onClick={() => router.back()} type="button">← 返回原来的学习位置</button>
      <header>
        <div><span>{character.pinyin}</span><h1>{character.character}</h1></div>
        <span className={`mastery-pill ${character.mastery_level}`}>{LEVEL_LABELS[character.mastery_level]}</span>
      </header>
      {error ? <p className="form-message form-error">{error}</p> : null}
      <section className="character-learning-content">
        <article><p className="eyebrow">简单解释</p><h2>{explanation || "请家长结合生活中的实物讲一讲。"}</h2></article>
        <article><p className="eyebrow">词语</p><div className="character-word-list">{words.length ? words.map((word) => <strong key={word}>{word}</strong>) : <span>暂无词语</span>}</div></article>
        <article><p className="eyebrow">简单句</p><h2>{sentence || `我们一起找一找“${character.character}”字。`}</h2></article>
        <article className="parent-learning-tip"><p className="eyebrow">家长提示</p><p>{parentTip || `在绘本、路牌或生活物品中找一找“${character.character}”，让孩子先观察再说。`}</p></article>
      </section>
      <div className="character-detail-actions">
        <button className="button button-primary" onClick={speak} type="button">再次朗读</button>
        <button className="button button-secondary" onClick={() => { setPracticeOpen(true); window.scrollTo({ top: 0, behavior: "smooth" }); }} type="button">再次学习</button>
        <button className="button button-secondary" onClick={() => setPracticeOpen((value) => !value)} type="button">再次练习</button>
        <button className="button button-secondary" disabled={working} onClick={() => void askAI()} type="button">{working ? "AI 正在讲解…" : "AI 儿童讲解"}</button>
      </div>
      {practiceOpen ? <aside className="character-practice"><strong>找字小游戏</strong><p>请在“{words.join("、") || character.character}”中指出“{character.character}”，再用它说一句自己的话。</p><small>这次自由练习不会重复计算今日完成数，也不会创建测评或修改掌握度。</small></aside> : null}
      {ai ? <p className="ai-boundary-note">以上讲解包含 AI 辅助内容（{ai.model}）；仅供学习参考，未修改识字掌握状态、测试成绩或学习记录。</p> : null}
    </main>
  );
}

export default function CharacterDetailPage() {
  return <ProtectedPage><CharacterDetailContent /></ProtectedPage>;
}
