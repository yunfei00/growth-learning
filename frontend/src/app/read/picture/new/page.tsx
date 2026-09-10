"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { ChangeEvent } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import { uploadFamilyPictureBook } from "@/lib/picture-book-api";

import styles from "./page.module.css";

type PageDraft = {
  file: File;
  text: string;
};

function sortFiles(files: File[]): File[] {
  return [...files].sort((left, right) =>
    left.name.localeCompare(right.name, "zh-CN", { numeric: true, sensitivity: "base" }),
  );
}

function FamilyPictureBookEditor() {
  const router = useRouter();
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [title, setTitle] = useState("");
  const [cover, setCover] = useState<File | null>(null);
  const [pages, setPages] = useState<PageDraft[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const previews = useMemo(
    () => pages.map((page) => ({ file: page.file, url: URL.createObjectURL(page.file) })),
    [pages],
  );

  if (status !== "ready" || !family || !activeChild) {
    return <main className={`${styles.page} section-shell`}>正在准备绘本编辑器…</main>;
  }

  const canCreate = family.current_role === "admin";

  const choosePages = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = sortFiles(Array.from(event.target.files ?? [])).slice(0, 24);
    setPages(selected.map((file) => ({ file, text: "" })));
    setError("");
  };

  const updatePageText = (index: number, text: string) => {
    setPages((current) =>
      current.map((page, pageIndex) => (pageIndex === index ? { ...page, text } : page)),
    );
  };

  const save = async () => {
    if (!canCreate || saving) return;
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("请填写绘本标题");
      return;
    }
    if (!pages.length) {
      setError("请选择正文图片");
      return;
    }
    if (pages.some((page) => !page.text.trim())) {
      setError("请把每一页的故事文字填写完整");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const result = await uploadFamilyPictureBook(activeChild.id, {
        title: cleanTitle,
        cover,
        images: pages.map((page) => page.file),
        pageTexts: pages.map((page) => page.text.trim()),
      });
      router.push(`/read/picture/${result.story_version_id}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "绘本保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className={`${styles.page} section-shell`}>
      <header className={styles.header}>
        <div>
          <p className="eyebrow">家庭绘本</p>
          <h1>添加自己的图片故事</h1>
          <p>适合把 AI 生成的《食海者》这类故事直接加入孩子的故事书。图片只保存在家庭私有空间。</p>
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

      {!canCreate ? <p className="form-message form-error">只有家庭管理员可以添加绘本。</p> : null}
      {error ? <p className="form-message form-error">{error}</p> : null}

      <section className={styles.editorCard}>
        <label className={styles.field}>
          <span>绘本标题</span>
          <input
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：食海者"
            value={title}
          />
        </label>

        <div className={styles.uploadGrid}>
          <label className={styles.uploadBox}>
            <strong>封面（可选）</strong>
            <span>{cover ? cover.name : "选择 1 张封面图"}</span>
            <input
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => setCover(event.target.files?.[0] ?? null)}
              type="file"
            />
          </label>
          <label className={styles.uploadBox}>
            <strong>正文图片</strong>
            <span>{pages.length ? `已选择 ${pages.length} 张` : "一次选择 1～24 张图片"}</span>
            <small>建议命名为 01、02、03…，系统会按文件名自动排序。</small>
            <input
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={choosePages}
              type="file"
            />
          </label>
        </div>

        {pages.length ? (
          <div className={styles.pageList}>
            <div className={styles.sectionHeading}>
              <div><strong>逐页填写文字</strong><span>图片和文字会一一对应</span></div>
              <span>{pages.length} 页</span>
            </div>
            {pages.map((page, index) => (
              <article className={styles.pageRow} key={`${page.file.name}-${page.file.lastModified}`}>
                <div className={styles.previewWrap}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img alt={`第 ${index + 1} 页预览`} src={previews[index]?.url} />
                  <span>第 {index + 1} 页 · {page.file.name}</span>
                </div>
                <label>
                  <span>这一页的故事文字</span>
                  <textarea
                    maxLength={220}
                    onChange={(event) => updatePageText(index, event.target.value)}
                    placeholder="例如：大海里，住着一只食海者。它有一张大大的嘴巴。"
                    rows={4}
                    value={page.text}
                  />
                  <small>{page.text.length}/220</small>
                </label>
              </article>
            ))}
          </div>
        ) : null}

        <div className={styles.tips}>
          <strong>保存后自动接入现有学习能力</strong>
          <span>逐页翻阅图片和文字，可选择显示拼音</span>
          <span>点击汉字查看拼音、解释和常用词</span>
          <span>语音服务已配置时，可听单页或连续朗读</span>
          <span>系统记录阅读完成情况，并分析孩子当前识字覆盖率</span>
        </div>

        <div className={styles.actions}>
          <button
            className="button button-primary"
            disabled={!canCreate || saving}
            onClick={() => void save()}
            type="button"
          >
            {saving ? "正在上传并创建绘本…" : "保存绘本并开始阅读"}
          </button>
          <Link className="button button-secondary" href="/read">返回故事书</Link>
        </div>
      </section>
    </main>
  );
}

export default function FamilyPictureBookPage() {
  return <ProtectedPage><FamilyPictureBookEditor /></ProtectedPage>;
}
