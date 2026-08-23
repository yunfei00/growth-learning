"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

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
  const searchParams = useSearchParams();
  const router = useRouter();
  const { activeChild } = useActiveChild();
  const [data, setData] = useState<CharacterMasteryPage | null>(null);
  const querySort = searchParams.get("sort");
  const initialSort: SortBy =
    querySort === "learning_time" || querySort === "recent_review" ? querySort : "character";
  const [sortBy, setSortBy] = useState<SortBy>(initialSort);
  const [page, setPage] = useState(Math.max(1, Number(searchParams.get("page") ?? "1") || 1));
  const [error, setError] = useState("");
  const level = params.level;
  const validLevel = level in LEVEL_LABELS;
  const sortOrder = sortBy === "character" ? "asc" : "desc";

  const load = useCallback(async () => {
    if (!activeChild || !validLevel) return;
    try {
      setData(
        await listCharacterMastery(activeChild.id, {
          masteryLevel: level,
          sortBy,
          sortOrder,
          page,
          pageSize: 40,
        }),
      );
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "汉字列表加载失败");
    }
  }, [activeChild, level, page, sortBy, sortOrder, validLevel]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const updateLocation = (nextSort: SortBy, nextPage: number) => {
    setSortBy(nextSort);
    setPage(nextPage);
    router.replace(`/learn/characters/status/${level}?sort=${nextSort}&page=${nextPage}`, {
      scroll: false,
    });
  };

  if (!validLevel) {
    return <main className="center-state section-shell"><p>没有这个掌握状态。</p><Link href="/learn/characters?view=overview">返回识字总览</Link></main>;
  }

  const returnTo = `/learn/characters/status/${level}?sort=${sortBy}&page=${page}`;
  return (
    <main className="character-status-page section-shell">
      <Link href="/learn/characters?view=overview">← 返回识字总览</Link>
      <header>
        <div><p className="eyebrow">识字总览详情</p><h1>{LEVEL_LABELS[level]}汉字</h1><p>共 {data?.total ?? "…"} 字，点击大字进入统一学习页，🔊 只负责朗读。</p></div>
        <label>排序
          <select value={sortBy} onChange={(event) => updateLocation(event.target.value as SortBy, 1)}>
            <option value="learning_time">学习时间</option>
            <option value="recent_review">最近复习</option>
            <option value="character">汉字</option>
          </select>
        </label>
      </header>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {!data ? <div className="center-state compact"><span className="loading-spinner" /></div> : (
        <>
          <div className="character-status-grid">
            {data.items.map((item) => (
              <CharacterLink
                className={`character-status-card level-${item.mastery_level}`}
                context={{
                  source: "mastery",
                  returnTo,
                  sequence: "mastery",
                  masteryLevel: level,
                  sortBy,
                  sortOrder,
                }}
                knowledgePointId={item.knowledge_point_id}
                key={item.knowledge_point_id}
                speakText={item.character}
              >
                <strong>{item.character}</strong>
                <small>{item.simple_meaning || "点击查看学习详情"}</small>
              </CharacterLink>
            ))}
            {data.items.length === 0 ? <p className="empty-note">这个状态下还没有汉字。</p> : null}
          </div>
          {data.pages > 1 ? (
            <nav aria-label="掌握状态汉字分页" className="history-pagination">
              <button disabled={page <= 1} onClick={() => updateLocation(sortBy, page - 1)} type="button">上一页</button>
              <span>{page} / {data.pages}</span>
              <button disabled={page >= data.pages} onClick={() => updateLocation(sortBy, page + 1)} type="button">下一页</button>
            </nav>
          ) : null}
        </>
      )}
    </main>
  );
}

export default function CharacterStatusPage() {
  return (
    <ProtectedPage>
      <Suspense fallback={<main className="center-state section-shell">正在加载汉字列表…</main>}>
        <CharacterStatusList />
      </Suspense>
    </ProtectedPage>
  );
}
