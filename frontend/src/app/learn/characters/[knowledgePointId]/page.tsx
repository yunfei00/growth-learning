"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type CharacterAIAssistance,
  type CharacterMasteryDetail,
  type CharacterNavigation,
  generateCharacterAIAssistance,
  getCharacterMasteryDetail,
  getCharacterNavigation,
} from "@/lib/api/client";
import {
  buildCharacterLearningHref,
  characterReturnLabel,
  parseCharacterLearningContext,
  resolveCharacterReturnAction,
} from "@/lib/character-navigation";
import { activateChineseSpeech, speakChinese } from "@/lib/speech";

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
  const searchParams = useSearchParams();
  const { activeChild } = useActiveChild();
  const [detail, setDetail] = useState<CharacterMasteryDetail | null>(null);
  const [navigation, setNavigation] = useState<CharacterNavigation | null>(null);
  const [ai, setAI] = useState<CharacterAIAssistance | null>(null);
  const [practiceOpen, setPracticeOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const serializedQuery = searchParams.toString();
  const context = useMemo(
    () => parseCharacterLearningContext(new URLSearchParams(serializedQuery)),
    [serializedQuery],
  );

  const load = useCallback(async () => {
    if (!activeChild) return;
    setDetail(null);
    setNavigation(null);
    setAI(null);
    setPracticeOpen(false);
    try {
      const detailValue = await getCharacterMasteryDetail(
        activeChild.id,
        params.knowledgePointId,
      );
      setDetail(detailValue);
      setError("");
      try {
        setNavigation(
          await getCharacterNavigation(activeChild.id, params.knowledgePointId, {
            sequence: context.sequence,
            contextId: context.contextId,
            itemKind: context.itemKind,
            masteryLevel: context.masteryLevel,
            priority: context.priority,
            sortBy: context.sortBy,
            sortOrder: context.sortOrder,
          }),
        );
      } catch {
        // A stale sequence must not prevent opening the reusable learning page.
        setNavigation(null);
      }
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "汉字详情加载失败");
    }
  }, [activeChild, context, params.knowledgePointId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

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

  const goBack = () => {
    const action = resolveCharacterReturnAction(context.returnTo, window.history.length > 1);
    if (action.kind === "history") router.back();
    else router.push(action.value);
  };

  if (!detail) {
    return <main className="center-state section-shell">{error || "正在打开汉字学习页…"}</main>;
  }
  const character = detail.state;
  const words = ai?.words ?? character.common_words;
  const explanation = ai?.simple_explanation ?? character.simple_meaning;
  const sentence = ai?.example_sentence ?? character.example_sentence;
  const parentTip = ai?.parent_tip ?? character.parent_tip;
  const sequenceLabel = navigation
    ? navigation.sequence === "system_path"
      ? `第 ${navigation.group} 组 · ${navigation.position} / ${navigation.total}`
      : `${navigation.position} / ${navigation.total}`
    : "单字学习";

  return (
    <main className="character-detail-page section-shell">
      <div className="character-detail-topline">
        <button className="character-back" onClick={goBack} type="button">
          ← {characterReturnLabel(context.source)}
        </button>
        <span>{sequenceLabel}</span>
      </div>
      {error ? <p className="form-message form-error">{error}</p> : null}
      <section className="character-learning-stage">
        <aside className="character-focus-panel">
          <p className="character-focus-pinyin">{character.pinyin}</p>
          <h1>{character.character}</h1>
          <button
            className="character-main-audio"
            onClick={() => speakChinese(character.character)}
            type="button"
          >
            <span aria-hidden="true">🔊</span> 朗读
          </button>
          <span className={`mastery-pill ${character.mastery_level}`}>
            {LEVEL_LABELS[character.mastery_level]}
          </span>
          <nav aria-label="汉字前后导航" className="character-sequence-nav">
            {navigation?.previous ? (
              <Link
                aria-label={`上一个汉字${navigation.previous.character}`}
                href={buildCharacterLearningHref(
                  navigation.previous.knowledge_point_id,
                  context,
                )}
              >
                <span>← 上一个</span>
                <strong>{navigation.previous.character}</strong>
              </Link>
            ) : (
              <span aria-disabled="true" className="disabled">← 上一个</span>
            )}
            {navigation?.next ? (
              <Link
                aria-label={`下一个汉字${navigation.next.character}`}
                href={buildCharacterLearningHref(navigation.next.knowledge_point_id, context)}
              >
                <span>下一个 →</span>
                <strong>{navigation.next.character}</strong>
              </Link>
            ) : (
              <span aria-disabled="true" className="disabled">已到最后</span>
            )}
          </nav>
        </aside>

        <div className="character-learning-content">
          <article>
            <p className="eyebrow">简单解释</p>
            <h2>{explanation || "请家长结合生活中的实物讲一讲。"}</h2>
          </article>
          <article>
            <p className="eyebrow">词语</p>
            <div className="character-word-list">
              {words.length ? (
                words.map((word) => (
                  <span key={word}>
                    <strong>{word}</strong>
                    <button
                      aria-label={`朗读${word}`}
                      onClick={(event) => activateChineseSpeech(event, word)}
                      type="button"
                    >
                      🔊
                    </button>
                  </span>
                ))
              ) : (
                <span>暂无词语</span>
              )}
            </div>
          </article>
          <article>
            <p className="eyebrow">简单句</p>
            <h2>{sentence || `我们一起找一找“${character.character}”字。`}</h2>
            <button
              className="inline-speech-button"
              onClick={() => speakChinese(sentence || `我们一起找一找${character.character}字。`)}
              type="button"
            >
              🔊 朗读句子
            </button>
          </article>
          <article className="parent-learning-tip">
            <p className="eyebrow">家长提示</p>
            <p>
              {parentTip ||
                `在绘本、路牌或生活物品中找一找“${character.character}”，让孩子先观察再说。`}
            </p>
          </article>
        </div>
      </section>

      <div className="character-detail-actions">
        <button className="button button-primary" onClick={() => speakChinese(character.character)} type="button">
          🔊 再次朗读
        </button>
        <button className="button button-secondary" onClick={() => setPracticeOpen(true)} type="button">
          再次学习
        </button>
        <button
          className="button button-secondary"
          onClick={() => setPracticeOpen((value) => !value)}
          type="button"
        >
          再次练习
        </button>
        <button
          className="button button-secondary"
          disabled={working}
          onClick={() => void askAI()}
          type="button"
        >
          {working ? "AI 正在讲解…" : "AI 儿童讲解"}
        </button>
      </div>
      {practiceOpen ? (
        <aside className="character-practice">
          <strong>找字小游戏</strong>
          <p>
            请在“{words.join("、") || character.character}”中指出“{character.character}”，再用它说一句自己的话。
          </p>
          <small>这次自由练习不会重复计算今日完成数，也不会创建测评或修改掌握度。</small>
        </aside>
      ) : null}
      {ai ? (
        <p className="ai-boundary-note">
          以上讲解包含 AI 辅助内容（{ai.model}）；仅供学习参考，未修改识字掌握状态、测试成绩或学习记录。
        </p>
      ) : null}
    </main>
  );
}

export default function CharacterDetailPage() {
  return (
    <ProtectedPage>
      <Suspense fallback={<main className="center-state section-shell">正在打开汉字学习页…</main>}>
        <CharacterDetailContent />
      </Suspense>
    </ProtectedPage>
  );
}
