"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { CharacterLink } from "@/components/character-link";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type CharacterMasteryPage,
  type MasteryLevel,
  listCharacterMastery,
} from "@/lib/api/client";

const LEVEL_LABELS: Record<MasteryLevel, string> = {
  unlearned: "未学习",
  introduced: "初识",
  recognizing: "基本认识",
  proficient: "熟练",
  stable: "稳定掌握",
};

type SortBy = "learning_time" | "recent_review" | "character";

function CharacterStatusList() {
  const params = useParams<{ level: MasteryLevel }>();
  const { activeChild } = useActiveChild();
  const [data, setData] = useState<CharacterMasteryPage | null>(null);
  const [sortBy, setSortBy] = useState<SortBy>("character");
  const [error, setError] = useState("");
  const level = params.level;
  const validLevel = level in LEVEL_LABELS;

  const load = useCallback(async () => {
    if (!activeChild || !validLevel) return;
    try {
      setData(await listCharacterMastery(activeChild.id, {
        masteryLevel: level,
        sortBy,
        sortOrder: sortBy === "character" ? "asc" : "desc",
        page: 1,
        pageSize: 100,
      }));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "汉字列表加载失败");
    }
  }, [activeChild, level, sortBy, validLevel]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (!validLevel) {
    return <main className="center-state section-shell"><p>没有这个掌握状态。</p><Link href="/learn/characters">返回识字总览</Link></main>;
  }

  return (
    <main className="character-status-page section-shell">
      <Link href="/learn/characters">← 返回识字总览</Link>
      <header>
        <div><p className="eyebrow">识字总览详情</p><h1>{LEVEL_LABELS[level]}汉字</h1><p>共 {data?.total ?? "…"} 字，每个汉字都可以继续进入儿童学习详情。</p></div>
        <label>排序
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortBy)}>
            <option value="learning_time">学习时间</option>
            <option value="recent_review">最近复习</option>
            <option value="character">汉字</option>
          </select>
        </label>
      </header>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {!data ? <div className="center-state compact"><span className="loading-spinner" /></div> : (
        <div className="character-status-grid">
          {data.items.map((item) => (
            <CharacterLink className={`character-status-card level-${item.mastery_level}`} knowledgePointId={item.knowledge_point_id} key={item.knowledge_point_id}>
              <strong>{item.character}</strong><span>{item.pinyin}</span><small>{item.simple_meaning || "点击查看学习详情"}</small>
            </CharacterLink>
          ))}
          {data.items.length === 0 ? <p className="empty-note">这个状态下还没有汉字。</p> : null}
        </div>
      )}
    </main>
  );
}

export default function CharacterStatusPage() {
  return <ProtectedPage><CharacterStatusList /></ProtectedPage>;
}
