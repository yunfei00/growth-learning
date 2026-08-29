"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  getCharacterMasterySummary,
  getEnglishOverview,
  getMathOverview,
  getPinyinOverview,
  getReadingSummary,
  listScienceRecommendations,
  type CharacterMasterySummary,
  type EnglishOverview,
  type MathOverview,
  type PinyinOverview,
  type ReadingSummary,
  type ScienceRecommendation,
} from "@/lib/api/client";

function LearningHubContent() {
  const { activeChild, children, setActiveChildId } = useActiveChild();
  const [characters, setCharacters] = useState<CharacterMasterySummary | null>(null);
  const [pinyin, setPinyin] = useState<PinyinOverview | null>(null);
  const [math, setMath] = useState<MathOverview | null>(null);
  const [english, setEnglish] = useState<EnglishOverview | null>(null);
  const [reading, setReading] = useState<ReadingSummary | null>(null);
  const [science, setScience] = useState<ScienceRecommendation[]>([]);
  const [errors, setErrors] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!activeChild) return;
    const timer = window.setTimeout(() => {
      setCharacters(null);
      setPinyin(null);
      setMath(null);
      setEnglish(null);
      setReading(null);
      setScience([]);
      setErrors({});
      void Promise.allSettled([
        getCharacterMasterySummary(activeChild.id),
        getPinyinOverview(activeChild.id),
        getMathOverview(activeChild.id),
        getEnglishOverview(activeChild.id),
        getReadingSummary(activeChild.id),
        listScienceRecommendations(activeChild.id),
      ]).then((results) => {
        const failed: Record<string, boolean> = {};
        const assign = <T,>(index: number, key: string, setter: (value: T) => void) => {
          const result = results[index];
          if (result.status === "fulfilled") setter(result.value as T);
          else failed[key] = true;
        };
        assign<CharacterMasterySummary>(0, "characters", setCharacters);
        assign<PinyinOverview>(1, "pinyin", setPinyin);
        assign<MathOverview>(2, "math", setMath);
        assign<EnglishOverview>(3, "english", setEnglish);
        assign<ReadingSummary>(4, "reading", setReading);
        assign<ScienceRecommendation[]>(5, "science", setScience);
        setErrors(failed);
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
            <span aria-hidden="true">字</span><div><h3>识字</h3><p>1200字学习路径</p><small>{characters ? `稳定掌握 ${characters.stable} / ${characters.total_enabled} 字` : errors.characters ? "识字进度暂时不可用" : "正在读取进度…"}</small></div>
          </Link>
          <Link className="learning-entry-card pinyin" href="/learn/pinyin">
            <span aria-hidden="true">ā</span><div><h3>拼音</h3><p>声母 · 韵母 · 声调 · 拼读</p><small>{pinyin ? `已学习 ${pinyin.learned} / ${pinyin.total} · 稳定 ${pinyin.stable}` : errors.pinyin ? "拼音进度暂时不可用" : "正在读取进度…"}</small></div>
          </Link>
          <Link className="learning-entry-card reading" href="/read">
            <span aria-hidden="true">读</span><div><h3>阅读</h3><p>故事与亲子阅读</p><small>{reading ? `本周阅读 ${reading.stories_read_this_week} 篇` : errors.reading ? "阅读进度暂时不可用" : "正在读取进度…"}</small></div>
          </Link>
        </div>
      </section>
      <section className="learning-subject-section">
        <div className="learning-subject-heading english"><span>A</span><div><h2>英语</h2><p>从听懂声音、图片和动作开始，再连接字母与自然拼读。</p></div></div>
        <div className="learning-entry-grid compact">
          <Link className="learning-entry-card english" href="/learn/english"><span aria-hidden="true">🔊</span><div><h3>英语启蒙</h3><p>词汇 · 字母 · Phonics · 短句</p><small>{english ? `听懂 ${english.understood_words} 词 · 字母 ${english.letters_learned} / ${english.letters_total} · Phonics ${english.phonics_practicing}` : errors.english ? "英语进度暂时不可用" : "正在读取进度…"}</small></div></Link>
        </div>
      </section>
      <section className="learning-subject-section">
        <div className="learning-subject-heading math"><span>数</span><div><h2>数学</h2><p>从数量、操作和图形开始，慢慢理解关系。</p></div></div>
        <div className="learning-entry-grid compact">
          <Link className="learning-entry-card math" href="/learn/math">
            <span aria-hidden="true">1·2·3</span><div><h3>数学启蒙</h3><p>数感 · 比较 · 规律 · 图形</p><small>{math ? `已学习 ${math.learned} / ${math.total} 个能力 · 稳定 ${math.stable}` : errors.math ? "数学进度暂时不可用" : "正在读取进度…"}</small></div>
          </Link>
        </div>
      </section>
      <section className="learning-subject-section">
        <div className="learning-subject-heading science"><span>科</span><div><h2>科学</h2><p>从生活里的问题开始观察和实验。</p></div></div>
        <div className="learning-entry-grid compact">
          <Link className="learning-entry-card science" href="/science"><span aria-hidden="true">🔬</span><div><h3>科学实验</h3><p>周末一起动手探索</p><small>{science[0] ? `${science[0].recently_completed ? "本周已完成" : "本周推荐"}：${science[0].experiment.title}` : errors.science ? "科学状态暂时不可用" : "正在读取本周状态…"}</small></div></Link>
        </div>
      </section>
    </main>
  );
}

export default function LearningHubPage() {
  return <ProtectedPage><LearningHubContent /></ProtectedPage>;
}
