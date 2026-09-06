"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { childFeedbackAudio } from "@/lib/child-feedback-audio";
import {
  type CharacterGlossary,
  type ReadingSession,
  type StoryVersion,
  completeReading,
  getStoryVersion,
  startReading,
} from "@/lib/api/client";
import {
  type PictureBookDetail,
  fetchPictureBookPageAudio,
  getPictureBook,
  picturePageImageUrl,
  preparePictureBookAudio,
} from "@/lib/picture-book-api";

import styles from "./page.module.css";

type SelectedCharacter = {
  character: string;
  pinyin: string;
  simple_meaning: string | null;
  common_words: string[];
};

function PictureBookReader() {
  const params = useParams<{ versionId: string }>();
  const { status, activeChild, family } = useActiveChild();
  const [book, setBook] = useState<PictureBookDetail | null>(null);
  const [story, setStory] = useState<StoryVersion | null>(null);
  const [session, setSession] = useState<ReadingSession | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [showPinyin, setShowPinyin] = useState(false);
  const [selected, setSelected] = useState<SelectedCharacter | null>(null);
  const [audioWorking, setAudioWorking] = useState(false);
  const [autoPlaying, setAutoPlaying] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const startingRef = useRef(false);
  const startedAtRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!activeChild || !params.versionId) return;
    try {
      const [bookValue, storyValue] = await Promise.all([
        getPictureBook(activeChild.id, params.versionId),
        getStoryVersion(activeChild.id, params.versionId),
      ]);
      setBook(bookValue);
      setStory(storyValue);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "绘本暂时无法打开");
    }
  }, [activeChild, params.versionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!activeChild || !book || session || startingRef.current) return;
    startingRef.current = true;
    void startReading(activeChild.id, book.story_version_id, "with_help")
      .then((value) => {
        setSession(value);
        startedAtRef.current = Date.now();
      })
      .catch(() => setMessage("阅读内容可以继续使用，但这次阅读进度暂时没有保存。"))
      .finally(() => {
        startingRef.current = false;
      });
  }, [activeChild, book, session]);

  useEffect(
    () => () => {
      audioRef.current?.pause();
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
      childFeedbackAudio.cancel();
    },
    [],
  );

  const glossary = useMemo(
    () => new Map<string, CharacterGlossary>(story?.glossary.map((item) => [item.character, item]) ?? []),
    [story],
  );

  const stopAudio = useCallback(() => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setAudioWorking(false);
    setAutoPlaying(false);
  }, []);

  const playBlob = async (blob: Blob) => {
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

  const loadPageAudio = async (index: number): Promise<Blob> => {
    if (!activeChild || !book) throw new Error("绘本尚未加载");
    try {
      return await fetchPictureBookPageAudio(activeChild.id, book.story_version_id, index);
    } catch (firstError) {
      if (family?.current_role !== "admin") throw firstError;
      setMessage("朗读还没准备好，正在生成一次并缓存…");
      await preparePictureBookAudio(activeChild.id, book.story_version_id);
      return await fetchPictureBookPageAudio(activeChild.id, book.story_version_id, index);
    }
  };

  const playPage = async (index: number) => {
    if (audioWorking) return;
    setAudioWorking(true);
    setMessage("正在准备这一页的朗读…");
    try {
      await playBlob(await loadPageAudio(index));
      setMessage("");
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "这一页暂时无法朗读");
    } finally {
      setAudioWorking(false);
    }
  };

  const playFromHere = async () => {
    if (!book || audioWorking) return;
    setAudioWorking(true);
    setAutoPlaying(true);
    setMessage("开始连续朗读…");
    try {
      for (let index = pageIndex; index < book.pages.length; index += 1) {
        setPageIndex(index);
        await playBlob(await loadPageAudio(index));
      }
      setMessage("整本朗读完成。");
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "连续朗读暂时中断了");
    } finally {
      setAudioWorking(false);
      setAutoPlaying(false);
    }
  };

  const selectCharacter = (character: string, pinyin: string) => {
    stopAudio();
    const detail = glossary.get(character);
    setSelected({
      character,
      pinyin,
      simple_meaning: detail?.simple_meaning ?? null,
      common_words: detail?.common_words ?? [],
    });
    childFeedbackAudio.speakInstruction(character);
  };

  const finishReading = async () => {
    if (!activeChild || !session || session.status === "completed") return;
    const startedAt = startedAtRef.current;
    try {
      const completed = await completeReading(activeChild.id, session.id, {
        duration_seconds: startedAt
          ? Math.max(1, Math.round((Date.now() - startedAt) / 1000))
          : undefined,
      });
      setSession(completed);
      setMessage("这本绘本读完了，阅读记录已经保存。");
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "阅读记录暂时没有保存成功");
    }
  };

  if (status !== "ready" || !activeChild || !book || !story) {
    return (
      <section className="center-state section-shell">
        {error ? <p className="form-message form-error">{error}</p> : <><span className="loading-spinner" /><p>正在打开绘本…</p></>}
      </section>
    );
  }

  const page = book.pages[pageIndex];
  const imageUrl = page.image_available
    ? picturePageImageUrl(activeChild.id, book.story_version_id, pageIndex)
    : null;

  return (
    <section className={`section-shell ${styles.reader}`}>
      <div className={styles.topbar}>
        <Link href="/read">← 我的故事书</Link>
        <label className="inline-toggle">
          <input checked={showPinyin} onChange={(event) => setShowPinyin(event.target.checked)} type="checkbox" />
          显示拼音
        </label>
      </div>

      <header className={styles.heading}>
        <p className="eyebrow">开放绘本 · Level {book.reading_level}</p>
        <h1>{book.title}</h1>
        <span>{pageIndex + 1} / {book.pages.length}</span>
      </header>

      <article className={styles.pageCard}>
        {imageUrl ? (
          <div
            aria-label={page.image_alt || `${book.title} 第 ${pageIndex + 1} 页插图`}
            className={styles.illustration}
            role="img"
            style={{ backgroundImage: `url(${imageUrl})` }}
          />
        ) : (
          <div className={`${styles.illustration} ${styles.noImage}`}>📖</div>
        )}

        <div className={styles.textArea}>
          <p className={styles.storyText}>
            {Array.from(page.text).map((character, index) => {
              const pinyin = page.pinyin[index];
              if (!pinyin) return <span key={`${index}-${character}`}>{character}</span>;
              return (
                <button
                  aria-label={`听“${character}”`}
                  className={styles.character}
                  key={`${index}-${character}`}
                  onClick={() => selectCharacter(character, pinyin)}
                  type="button"
                >
                  {showPinyin ? <ruby>{character}<rt>{pinyin}</rt></ruby> : character}
                </button>
              );
            })}
          </p>

          <div className={styles.audioActions}>
            <button className="button button-secondary" disabled={audioWorking} onClick={() => void playPage(pageIndex)} type="button">🔊 听这一页</button>
            <button className="button button-secondary" disabled={audioWorking} onClick={() => void playFromHere()} type="button">▶ 连续朗读</button>
            <button className="button button-secondary" disabled={!audioWorking} onClick={stopAudio} type="button">■ 停止</button>
          </div>
          {message ? <small className={styles.message}>{autoPlaying ? `连续朗读 · ${message}` : message}</small> : null}
        </div>
      </article>

      <nav className={styles.navigation} aria-label="绘本翻页">
        <button disabled={pageIndex === 0} onClick={() => { stopAudio(); setSelected(null); setPageIndex((value) => Math.max(0, value - 1)); }} type="button">← 上一页</button>
        <span>{pageIndex + 1} / {book.pages.length}</span>
        <button disabled={pageIndex === book.pages.length - 1} onClick={() => { stopAudio(); setSelected(null); setPageIndex((value) => Math.min(book.pages.length - 1, value + 1)); }} type="button">下一页 →</button>
      </nav>

      {selected ? (
        <aside className={styles.wordCard} aria-live="polite">
          <button aria-label="关闭字卡" className={styles.close} onClick={() => setSelected(null)} type="button">×</button>
          <strong>{selected.character}</strong>
          <span>{selected.pinyin}</span>
          <p>{selected.simple_meaning ?? "这个字暂时没有字库解释，可以先听读音继续阅读。"}</p>
          {selected.common_words.length ? <small>常用词：{selected.common_words.join("、")}</small> : null}
          <button className="button button-secondary" onClick={() => childFeedbackAudio.speakInstruction(selected.character)} type="button">🔊 再听一次</button>
        </aside>
      ) : null}

      <div className={styles.finishRow}>
        <button className="button button-primary" disabled={!session || session.status === "completed"} onClick={() => void finishReading()} type="button">
          {session?.status === "completed" ? "✓ 已记录读完" : "我读完这本绘本了"}
        </button>
      </div>

      <footer className={styles.attribution}>
        <strong>内容来源与许可</strong>
        <span>来源：Global Digital Library · {book.license_name}</span>
        {Array.isArray(book.attribution.authors) && book.attribution.authors.length ? <span>作者：{book.attribution.authors.join("、")}</span> : null}
        {typeof book.attribution.publisher === "string" && book.attribution.publisher ? <span>出版/提供：{book.attribution.publisher}</span> : null}
        <a href={book.source_url} rel="noreferrer" target="_blank">查看原始作品与完整署名</a>
        <small>本系统只记录阅读接触和求助行为；点字、听音不会自动把汉字判定为“认识”。</small>
      </footer>
    </section>
  );
}

export default function PictureBookPage() {
  return <ProtectedPage><PictureBookReader /></ProtectedPage>;
}
