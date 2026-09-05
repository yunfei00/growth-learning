"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import { createParentStory } from "@/lib/manual-story-api";

import styles from "./page.module.css";

function ParentStoryEditor() {
  const router = useRouter();
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  if (status !== "ready" || !family || !activeChild) {
    return <main className={`${styles.page} section-shell`}>正在准备故事编辑器…</main>;
  }

  const canCreate = family.current_role === "admin";

  const save = async () => {
    if (!canCreate || saving) return;
    if (!title.trim() || !content.trim()) {
      setError("请填写故事标题和内容");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await createParentStory(activeChild.id, {
        title: title.trim(),
        content: content.trim(),
      });
      router.push(`/read/${result.version.id}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "故事保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className={`${styles.page} section-shell`}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">辅助阅读</p>
          <h1>家长添加故事</h1>
          <p>
            直接粘贴一篇适合孩子的故事。这里不设置识字量门槛，系统只分析当前识字覆盖率，
            不会因为生字多而拒绝保存。
          </p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={(id) => {
            setActiveChildId(id);
            setError("");
          }}
        />
      </header>

      {!canCreate ? (
        <p className="form-message form-error">只有家庭管理员可以添加故事。</p>
      ) : null}
      {error ? <p className="form-message form-error">{error}</p> : null}

      <section className={styles.editorCard}>
        <label>
          <span>故事标题</span>
          <input
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：小熊找春天"
            value={title}
          />
        </label>
        <label>
          <span>故事内容</span>
          <textarea
            maxLength={5000}
            onChange={(event) => setContent(event.target.value)}
            placeholder={"把故事粘贴在这里。\n可以一段一行，保存后孩子可以逐段阅读和听朗读。"}
            rows={14}
            value={content}
          />
        </label>
        <div className={styles.tips}>
          <strong>保存后系统会自动做什么？</strong>
          <span>分析这篇故事中孩子目前认识、可能认识和暂未掌握的汉字</span>
          <span>把字库中出现的汉字做成可点击提示：拼音、解释、常用词</span>
          <span>如果百炼语音服务可用，会自动生成并缓存每一段朗读音频</span>
          <span>阅读只记录故事接触，不会把故事里的字自动判定为“已经认识”</span>
        </div>
        <div className={styles.actions}>
          <button
            className="button button-primary"
            disabled={!canCreate || saving}
            onClick={() => void save()}
            type="button"
          >
            {saving ? "正在保存并准备朗读…" : "保存故事并开始阅读"}
          </button>
          <Link className="button button-secondary" href="/read">
            返回故事书
          </Link>
        </div>
      </section>
    </main>
  );
}

export default function ParentStoryPage() {
  return (
    <ProtectedPage>
      <ParentStoryEditor />
    </ProtectedPage>
  );
}
