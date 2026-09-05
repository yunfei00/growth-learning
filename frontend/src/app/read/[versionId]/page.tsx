"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { childFeedbackAudio } from "@/lib/child-feedback-audio";
import {
  ApiClientError,
  type CharacterGlossary,
  type ReadingSession,
  type StoryVersion,
  completeReading,
  getStoryVersion,
  startReading,
  submitReadingAnswers,
} from "@/lib/api/client";
import { fetchStoryParagraphAudio, prepareStoryAudio } from "@/lib/manual-story-api";

function messageFrom(error: unknown, fallback: string) {
  return error instanceof ApiClientError || error instanceof Error ? error.message : fallback;
}

type StoryTextProps = {
  paragraph: string;
  glossary: Map<string, CharacterGlossary>;
  targets: Set<string>;
  showPinyin: boolean;
  onCharacterTap: (detail: CharacterGlossary) => void;
};

function StoryText({ paragraph, glossary, targets, showPinyin, onCharacterTap }: StoryTextProps) {
  return (
    <>
      {Array.from(paragraph).map((character, index) => {
        const detail = glossary.get(character);
        const className = targets.has(character) ? "story-character target" : "story-character";
        if (!detail) return <span key={`${index}-${character}`}>{character}</span>;
        return (
          <button
            aria-label={`听“${character}”并查看解释`}
            className={className}
            key={`${index}-${character}`}
            onClick={() => onCharacterTap(detail)}
            type="button"
          >
            {showPinyin ? <ruby>{character}<rt>{detail.pinyin}</rt></ruby> : character}
          </button>
        );
      })}
    </>
  );
}

function StoryReader() {
  const params = useParams<{ versionId: string }>();
  const { activeChild, family } = useActiveChild();
  const [story, setStory] = useState<StoryVersion | null>(null);
  const [session, setSession] = useState<ReadingSession | null>(null);
  const [mode, setMode] = useState<"independent" | "with_help">("with_help");
  const [showPinyin, setShowPinyin] = useState(false);
  const [selectedGlossary, setSelectedGlossary] = useState<CharacterGlossary | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [helped, setHelped] = useState<Record<string, boolean>>({});
  const [parentNote, setParentNote] = useState("");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [audioWorking, setAudioWorking] = useState(false);
  const [playingParagraph, setPlayingParagraph] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [audioMessage, setAudioMessage] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!activeChild || !params.versionId) return;
    try {
      setStory(await getStoryVersion(activeChild.id, params.versionId));
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "暂时无法打开这篇故事"));
    }
  }, [activeChild, params.versionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(
    () => () => {
      audioRef.current?.pause();
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
      childFeedbackAudio.cancel();
    },
    [],
  );

  const stopAudio = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    setAudioWorking(false);
    setPlayingParagraph(null);
    setAudioMessage("");
  }, []);

  const selectCharacter = useCallback(
    (detail: CharacterGlossary) => {
      stopAudio();
      setSelectedGlossary(detail);
      childFeedbackAudio.speakInstruction(detail.character);
    },
    [stopAudio],
  );

  const glossary = useMemo(
    () => new Map(story?.glossary.map((item) => [item.character, item]) ?? []),
    [story],
  );
  const targets = useMemo(() => new Set(story?.target_characters ?? []), [story]);

  if (!activeChild || !story) {
    return (
      <section className="center-state section-shell">
        {error ? <p className="form-message form-error">{error}</p> : <><span className="loading-spinner" aria-hidden="true" /><p>正在打开故事…</p></>}
      </section>
    );
  }

  const manualStory = story.provider === "parent_manual";

  const begin = async () => {
    setIsWorking(true);
    try {
      const value = await startReading(activeChild.id, story.id, mode);
      setSession(value);
      setStartedAt(Date.now());
      setMessage(value.status === "in_progress" ? "阅读进度已保存，可以随时离开后继续。" : "这篇故事已完成。" );
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "无法开始阅读"));
    } finally {
      setIsWorking(false);
    }
  };

  const submitAndFinish = async () => {
    if (!session) return;
    const unanswered = story.questions.filter(
      (question) => !session.answers.some((answer) => answer.question_id === question.id),
    );
    if (unanswered.some((question) => answers[question.id] === undefined)) {
      setError("请先完成全部阅读理解题");
      return;
    }
    setIsWorking(true);
    setError("");
    try {
      let current = session;
      if (unanswered.length > 0) {
        current = await submitReadingAnswers(
          activeChild.id,
          session.id,
          unanswered.map((question) => ({
            question_id: question.id,
            selected_option_index: answers[question.id],
            outcome: helped[question.id] ? "with_help" : "correct",
          })),
        );
      }
      current = await completeReading(activeChild.id, current.id, {
        duration_seconds: startedAt ? Math.max(1, Math.round((Date.now() - startedAt) / 1000)) : undefined,
        parent_note: parentNote.trim() || undefined,
      });
      setSession(current);
      setMessage(`阅读完成，已记录 ${current.story_exposure_count} 个目标字的故事接触；不会产生“认字正确”证据。`);
    } catch (requestError) {
      setError(messageFrom(requestError, "阅读记录没有保存成功"));
    } finally {
      setIsWorking(false);
    }
  };

  const playBlob = async (blob: Blob): Promise<void> => {
    audioRef.current?.pause();
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    const objectUrl = URL.createObjectURL(blob);
    audioUrlRef.current = objectUrl;
    const audio = new Audio(objectUrl);
    audioRef.current = audio;
    await new Promise<void>((resolve, reject) => {
      audio.addEventListener("ended", () => resolve(), { once: true });
      audio.addEventListener("error", () => reject(new Error("音频播放失败")), { once: true });
      void audio.play().catch(reject);
    });
    URL.revokeObjectURL(objectUrl);
    if (audioUrlRef.current === objectUrl) audioUrlRef.current = null;
  };

  const loadParagraphAudio = async (index: number): Promise<Blob> => {
    try {
      return await fetchStoryParagraphAudio(activeChild.id, story.id, index);
    } catch (firstError) {
      if (!manualStory || family?.current_role !== "admin") throw firstError;
      setAudioMessage("朗读音频还没准备好，正在自动生成…");
      await prepareStoryAudio(activeChild.id, story.id);
      return await fetchStoryParagraphAudio(activeChild.id, story.id, index);
    }
  };

  const playParagraph = async (index: number) => {
    if (audioWorking) return;
    setAudioWorking(true);
    setPlayingParagraph(index);
    setAudioMessage("正在准备朗读…");
    try {
      await playBlob(await loadParagraphAudio(index));
      setAudioMessage("");
    } catch (requestError) {
      setAudioMessage(messageFrom(requestError, "这段朗读暂时不可用，可以继续自己读。"));
    } finally {
      setPlayingParagraph(null);
      setAudioWorking(false);
    }
  };

  const playAll = async () => {
    if (audioWorking) return;
    setAudioWorking(true);
    setAudioMessage("开始朗读全文…");
    try {
      for (let index = 0; index < story.paragraphs.length; index += 1) {
        setPlayingParagraph(index);
        await playBlob(await loadParagraphAudio(index));
      }
      setAudioMessage("全文朗读完成。");
    } catch (requestError) {
      setAudioMessage(messageFrom(requestError, "全文朗读暂时不可用，可以逐段阅读。"));
    } finally {
      setPlayingParagraph(null);
      setAudioWorking(false);
    }
  };

  return (
    <section className="reader-page section-shell">
      <div className="reader-topbar">
        <Link href="/read">← 我的故事书</Link>
        <label className="inline-toggle"><input checked={showPinyin} onChange={(event) => setShowPinyin(event.target.checked)} type="checkbox" />显示拼音</label>
      </div>
      <header className="story-heading">
        <p className="eyebrow">{manualStory ? "家长添加 · 辅助阅读" : `版本 ${story.version_number} · ${story.difficulty}`}</p>
        <h1>{story.title}</h1>
        <div className="coverage-strip">
          {manualStory ? <span>不设识字量门槛</span> : <span>目标覆盖 {(story.requested_known_coverage * 100).toFixed(0)}%</span>}
          <strong>当前已知覆盖 {(story.actual_usable_known_coverage * 100).toFixed(1)}%</strong>
          {manualStory ? <span>暂未掌握字 {story.unexpected_characters.length} 个</span> : <span>目标字 {story.target_characters.join("、")}</span>}
        </div>
      </header>

      {manualStory ? (
        <section className="reading-start-card">
          <strong>🔊 故事朗读</strong>
          <p>朗读音频由服务器生成后缓存，不会每次播放都重新调用模型。</p>
          <div className="mode-buttons">
            <button disabled={audioWorking} onClick={() => void playAll()} type="button">▶ 听全文</button>
            <button disabled={!audioWorking} onClick={stopAudio} type="button">■ 停止</button>
          </div>
          {audioMessage ? <small>{audioMessage}</small> : null}
        </section>
      ) : null}

      {!session ? (
        <div className="reading-start-card">
          <strong>准备好了吗？</strong>
          <p>拼音默认关闭。轻点故事中的汉字会直接读出来，并打开拼音、解释和常用词。</p>
          <div className="mode-buttons">
            <button className={mode === "independent" ? "selected" : ""} onClick={() => setMode("independent")} type="button">独立阅读</button>
            <button className={mode === "with_help" ? "selected" : ""} onClick={() => setMode("with_help")} type="button">家长陪读</button>
          </div>
          <button className="button button-primary" disabled={isWorking} onClick={() => void begin()} type="button">{isWorking ? "正在保存进度…" : "开始 / 继续阅读"}</button>
        </div>
      ) : null}

      <article className="story-paper">
        {story.paragraphs.map((paragraph, index) => (
          <div className="story-paragraph-block" key={index}>
            <p>
              <StoryText
                glossary={glossary}
                onCharacterTap={selectCharacter}
                paragraph={paragraph}
                showPinyin={showPinyin}
                targets={targets}
              />
            </p>
            {manualStory ? (
              <button
                className="button button-secondary"
                disabled={audioWorking}
                onClick={() => void playParagraph(index)}
                type="button"
              >
                {playingParagraph === index ? "🔊 正在朗读…" : "🔊 听这一段"}
              </button>
            ) : null}
          </div>
        ))}
      </article>

      {selectedGlossary ? (
        <aside className="character-popover" aria-live="polite">
          <button aria-label="关闭" onClick={() => setSelectedGlossary(null)} type="button">×</button>
          <strong>{selectedGlossary.character}</strong><span>{selectedGlossary.pinyin}</span>
          <p>{selectedGlossary.simple_meaning ?? "字库暂时没有简单解释"}</p>
          <small>常用词：{selectedGlossary.common_words.join("、") || "暂无"}</small>
          <button
            className="button button-secondary"
            onClick={() => childFeedbackAudio.speakInstruction(selectedGlossary.character)}
            type="button"
          >
            🔊 再听一次
          </button>
        </aside>
      ) : null}

      {session ? (
        <section className="comprehension-panel">
          <p className="eyebrow">{story.questions.length ? "阅读理解" : "阅读记录"}</p>
          <h2>{story.questions.length ? "和孩子聊一聊故事" : "读完以后保存这次阅读"}</h2>
          {story.questions.map((question) => {
            const saved = session.answers.find((answer) => answer.question_id === question.id);
            return (
              <fieldset disabled={Boolean(saved) || session.status === "completed"} key={question.id}>
                <legend>{question.position + 1}. {question.question}</legend>
                {question.options.map((option, index) => (
                  <label key={option}><input checked={(saved?.selected_option_index ?? answers[question.id]) === index} name={question.id} onChange={() => setAnswers((current) => ({ ...current, [question.id]: index }))} type="radio" />{option}</label>
                ))}
                {mode === "with_help" && !saved ? <label className="helped-answer"><input checked={helped[question.id] ?? false} onChange={(event) => setHelped((current) => ({ ...current, [question.id]: event.target.checked }))} type="checkbox" />这题在帮助下完成</label> : null}
                {saved ? <small>已保存：{saved.outcome}</small> : null}
              </fieldset>
            );
          })}
          <label className="parent-note">家长备注（可选）<textarea maxLength={1000} onChange={(event) => setParentNote(event.target.value)} value={parentNote} /></label>
          {error ? <p className="form-message form-error">{error}</p> : null}
          {message ? <p className="form-message form-success">{message}</p> : null}
          <button className="button button-primary" disabled={isWorking || session.status === "completed"} onClick={() => void submitAndFinish()} type="button">{session.status === "completed" ? "已完成阅读" : isWorking ? "正在保存…" : "完成阅读并保存"}</button>
          <p className="evidence-note">读完只记录故事接触，不会自动把故事中的汉字标记为“认识”或“答对”。</p>
        </section>
      ) : null}

      <section className="coverage-details">
        <strong>程序计算的真实汉字覆盖</strong>
        <span>全文汉字 {story.total_han_occurrences}</span>
        <span>不同汉字 {story.unique_han_count}</span>
        <span>当前已知覆盖 {(story.actual_usable_known_coverage * 100).toFixed(1)}%</span>
        <span>暂未掌握覆盖 {(story.actual_unexpected_coverage * 100).toFixed(1)}%</span>
        <small>分析器 {story.analyzer_version} · 策略 {story.coverage_policy_version} · 识字快照 {new Date(story.snapshot_at).toLocaleString("zh-CN")}</small>
      </section>
    </section>
  );
}

export default function StoryVersionPage() {
  return <ProtectedPage><StoryReader /></ProtectedPage>;
}