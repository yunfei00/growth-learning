"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  getCharacterMasterySummary,
  getMathOverview,
  getPinyinOverview,
  type CharacterMasterySummary,
  type MathOverview,
  type PinyinOverview,
} from "@/lib/api/client";

function LearningHubContent() {
  const { activeChild, children, setActiveChildId } = useActiveChild();
  const [characters, setCharacters] = useState<CharacterMasterySummary | null>(null);
  const [pinyin, setPinyin] = useState<PinyinOverview | null>(null);
  const [math, setMath] = useState<MathOverview | null>(null);

  useEffect(() => {
    if (!activeChild) return;
    const timer = window.setTimeout(() => {
      void Promise.all([
        getCharacterMasterySummary(activeChild.id),
        getPinyinOverview(activeChild.id),
        getMathOverview(activeChild.id),
      ]).then(([characterValue, pinyinValue, mathValue]) => {
        setCharacters(characterValue);
        setPinyin(pinyinValue);
        setMath(mathValue);
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeChild]);

  return (
    <main className="learning-hub-page section-shell">
      <header className="learning-hub-header">
        <div><p className="eyebrow">学习</p><h1>今天想从哪里开始？</h1><p>每次一点点，听、看、练习都算认真成长。</p></div>
        <ChildSwitcher
          activeChildId={activeChild?.id ?? ""}
          childOptions={children}
          onChange={setActiveChildId}
        />
      </header>
      <section className="learning-subject-section">
        <div className="learning-subject-heading"><span>语</span><div><h2>语文</h2><p>识字、拼音与阅读互相陪伴，但各自保留真实进度。</p></div></div>
        <div className="learning-entry-grid">
          <Link className="learning-entry-card characters" href="/learn/characters">
            <span aria-hidden="true">字</span><div><h3>识字</h3><p>1200字学习路径</p><small>{characters ? `稳定掌握 ${characters.stable} 字` : "正在读取进度…"}</small></div>
          </Link>
          <Link className="learning-entry-card pinyin" href="/learn/pinyin">
            <span aria-hidden="true">ā</span><div><h3>拼音</h3><p>声母 · 韵母 · 声调 · 拼读</p><small>{pinyin ? `已学习 ${pinyin.learned} / ${pinyin.total}` : "正在读取进度…"}</small></div>
          </Link>
          <Link className="learning-entry-card reading" href="/read">
            <span aria-hidden="true">读</span><div><h3>阅读</h3><p>故事与亲子阅读</p><small>使用真正学过的汉字读故事</small></div>
          </Link>
        </div>
      </section>
      <section className="learning-subject-section">
        <div className="learning-subject-heading math"><span>数</span><div><h2>数学</h2><p>从数量、操作和图形开始，慢慢理解关系。</p></div></div>
        <div className="learning-entry-grid compact">
          <Link className="learning-entry-card math" href="/learn/math">
            <span aria-hidden="true">1·2·3</span><div><h3>数学启蒙</h3><p>数感 · 比较 · 规律 · 图形</p><small>{math ? `已学习 ${math.learned} / ${math.total} 个能力` : "正在读取进度…"}</small></div>
          </Link>
        </div>
      </section>
      <section className="learning-subject-section">
        <div className="learning-subject-heading science"><span>科</span><div><h2>科学</h2><p>从生活里的问题开始观察和实验。</p></div></div>
        <div className="learning-entry-grid compact">
          <Link className="learning-entry-card science" href="/science"><span aria-hidden="true">🔬</span><div><h3>科学实验</h3><p>周末一起动手探索</p></div></Link>
          <article className="learning-entry-card unavailable"><span aria-hidden="true">A</span><div><h3>英语</h3><p>暂未配置课程</p></div></article>
        </div>
      </section>
    </main>
  );
}

export default function LearningHubPage() {
  return <ProtectedPage><LearningHubContent /></ProtectedPage>;
}
