"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import { type GrowthBook, getGrowthBook } from "@/lib/api/client";

function PrintBook() {
  const params = useParams<{ bookId: string }>();
  const { activeChild } = useActiveChild();
  const [book, setBook] = useState<GrowthBook | null>(null);

  useEffect(() => {
    if (activeChild) void getGrowthBook(activeChild.id, params.bookId).then(setBook);
  }, [activeChild, params.bookId]);

  if (!book || !activeChild) return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在打开成长册…</p></section>;
  const snapshotEvents = Array.isArray(book.snapshot.events) ? book.snapshot.events as Array<Record<string, string>> : [];
  const facts = (book.snapshot.facts || {}) as Record<string, number>;
  return <article className="growth-book-print">
    <button className="button button-primary no-print" onClick={() => window.print()} type="button">打印 / 保存为 PDF</button>
    <header><p>成长学习 · 私有家庭档案</p><h1>{book.title}</h1><h2>{activeChild.nickname || activeChild.display_name}</h2><small>版本 {book.version_number} · {new Date(book.created_at).toLocaleDateString("zh-CN")}</small></header>
    <section className="book-facts"><article><strong>{facts.stories_completed ?? 0}</strong><span>篇故事阅读</span></article><article><strong>{facts.science_experiments_completed ?? 0}</strong><span>次科学实验</span></article></section>
    <section><h2>这一年的成长瞬间</h2>{snapshotEvents.map((event) => <article className="book-memory" key={event.id}><time>{new Date(event.occurred_at).toLocaleDateString("zh-CN")}</time><h3>{event.title}</h3><p>{event.body}</p></article>)}{snapshotEvents.length === 0 ? <p>尚未为这一版选择成长事件。</p> : null}</section>
    {book.parent_message ? <blockquote><strong>家人的寄语</strong><p>{book.parent_message}</p><small>{book.message_recorded_at ? new Date(book.message_recorded_at).toLocaleDateString("zh-CN") : ""}</small></blockquote> : null}
    <footer>这是一册真实回忆，不是成绩单，也不包含全局成长分数。</footer>
  </article>;
}

export default function GrowthBookPrintPage() {
  return <ProtectedPage><PrintBook /></ProtectedPage>;
}
