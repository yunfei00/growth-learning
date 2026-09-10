"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  type OpenPictureBook,
  importOpenPictureBook,
  listOpenPictureBooks,
} from "@/lib/picture-book-api";

import styles from "./page.module.css";

function OnlinePictureBookLibrary() {
  const router = useRouter();
  const { status, activeChild, family } = useActiveChild();
  const [level, setLevel] = useState<"1" | "2">("1");
  const [books, setBooks] = useState<OpenPictureBook[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    setLoading(true);
    try {
      setBooks(await listOpenPictureBooks(activeChild.id, level));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "在线绘本库暂时无法加载");
    } finally {
      setLoading(false);
    }
  }, [activeChild, level]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !activeChild || !family) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在打开在线绘本库…</p></section>;
  }

  const canImport = family.current_role === "admin";
  const handleImport = async (book: OpenPictureBook) => {
    if (!canImport || importing) return;
    setImporting(book.source_book_id);
    setError("");
    try {
      const result = await importOpenPictureBook(activeChild.id, book.source_book_id);
      router.push(`/read/picture/${result.story_version_id}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "绘本导入失败，请稍后重试");
    } finally {
      setImporting(null);
    }
  };

  return (
    <section className={`section-shell ${styles.library}`}>
      <div className={styles.topbar}>
        <div>
          <p className="eyebrow">开放绘本</p>
          <h1>在线绘本库</h1>
          <p>先从 Global Digital Library 的简体中文开放绘本开始。加入书架后，图片、文字和朗读都保存在家庭私有阅读空间。</p>
        </div>
        <div className={styles.actions}>
          {canImport ? <Link className="button button-primary" href="/read/picture/new">＋ 添加自己的绘本</Link> : null}
          <Link href="/read">← 返回我的故事书</Link>
        </div>
      </div>

      <div className={styles.notice}>
        <strong>也可以加入你自己制作的 AI 图片故事</strong>
        <span>例如《食海者》：封面单独上传，正文图片可一次多选，并逐页填写故事文字。</span>
      </div>

      <div className={styles.levels} role="group" aria-label="阅读级别">
        <button className={level === "1" ? styles.selected : ""} onClick={() => setLevel("1")} type="button">
          <strong>Level 1</strong><span>简单词语 · 重复较多</span>
        </button>
        <button className={level === "2" ? styles.selected : ""} onClick={() => setLevel("2")} type="button">
          <strong>Level 2</strong><span>故事更完整 · 下一阶段</span>
        </button>
      </div>

      <div className={styles.notice}>
        <strong>只展示许可明确的开放内容</strong>
        <span>当前仅允许 CC BY 4.0 / CC BY-SA 4.0。来源与署名会跟随绘本保存，不使用第三方现成朗读音频。</span>
      </div>

      {error ? <p className="form-message form-error">{error}</p> : null}
      {loading ? <div className={styles.loading}><span className="loading-spinner" /><p>正在获取中文绘本…</p></div> : null}

      {!loading && books.length === 0 ? (
        <div className={styles.empty}><strong>这个级别暂时没有符合许可要求的中文绘本</strong><p>可以切换另一个级别，稍后也可以继续接入更多开放来源。</p></div>
      ) : null}

      <div className={styles.grid}>
        {books.map((book) => (
          <article className={styles.card} key={book.source_book_id}>
            <div
              aria-label={`${book.title} 封面`}
              className={styles.cover}
              role="img"
              style={book.thumbnail_url ? { backgroundImage: `url(${JSON.stringify(book.thumbnail_url).slice(1, -1)})` } : undefined}
            >
              {!book.thumbnail_url ? <span>📖</span> : null}
            </div>
            <div className={styles.cardBody}>
              <div className={styles.badges}><span>Level {book.reading_level}</span><span>{book.license_name}</span></div>
              <h2>{book.title}</h2>
              {book.description ? <p>{book.description}</p> : <p>适合亲子共读与辅助阅读的开放中文绘本。</p>}
              <small>
                {book.authors.length ? `作者：${book.authors.join("、")}` : "作者信息以原始来源为准"}
                {book.publisher ? ` · ${book.publisher}` : ""}
              </small>
              <div className={styles.actions}>
                <a href={book.source_url} rel="noreferrer" target="_blank">查看原始来源</a>
                <button
                  className="button button-primary"
                  disabled={!canImport || Boolean(importing)}
                  onClick={() => void handleImport(book)}
                  type="button"
                >
                  {importing === book.source_book_id ? "正在加入书架…" : canImport ? "＋ 加入我的书架" : "管理员可加入"}
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function OnlinePictureBookPage() {
  return <ProtectedPage><OnlinePictureBookLibrary /></ProtectedPage>;
}
