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
  pageNumber: number;
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
    setPages(selected.map((file, index) => ({ file, text: "", pageNumber: index + 1 })));
    setError("");
  };

  const updatePageText = (index: number, text: string) => {
    setPages((current) =>
      current.map((page, pageIndex) => (pageIndex === index ? { ...page, text } : page)),
    );
  };

  const updatePageNumber = (index: number, value: number) => {
    setPages((current) =>
      current.map((page, pageIndex) =>
        pageIndex === index ? { ...page, pageNumber: value } : page,
      ),
    );
    setError("");
  };

  const validatePageNumbers = () => {
    const numbers = pages.map((page) => page.pageNumber);
    if (numbers.some((number) => !Number.isInteger(number) || number < 1 || number > pages.length)) {
      setError(`页码必须是 1～${pages.length} 的整数`);
      return false;
    }
    if (new Set(numbers).size !== numbers.length) {
      setError("页码不能重复，请确保每张图片都有唯一页码");
      return false;
    }
    return true;
  };

  const applyPageOrder = () => {
    if (!validatePageNumbers()) return;
    setPages((current) =>
      [...current]
        .sort((left, right) => left.pageNumber - right.pageNumber)
        .map((page, index) => ({ ...page, pageNumber: index + 1 })),
    );
    setError("");
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
    if (!validatePageNumbers()) return;

    const orderedPages = [...pages].sort((left, right) => left.pageNumber - right.pageNumber);
    setSaving(true);
    setError("");
    try {
      const result = await uploadFamilyPictureBook(activeChild.id, {
        title: cleanTitle,
        cover,
        images: orderedPages.map((page) => page.file),
        pageTexts: orderedPages.map((page) => page.text.trim()),
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
            <small>系统会先按文件名排序；如果识别顺序不对，可以在下面手动指定每张图是第几页。</small>
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
              <div>
                <strong>检查页面顺序并填写文字</strong>
                <span>页码可以手动修改；最终保存时严格按这里的页码排列。</span>
              </div>
              <div className={styles.orderActions}>
                <span>{pages.length} 页</span>
                <button className="button button-secondary" onClick={applyPageOrder} type="button">
                  ↕ 按页码重新排列预览
                </button>
              </div>
            </div>
            {pages.map((page, index) => (
              <article className={styles.pageRow} key={`${page.file.name}-${page.file.lastModified}`}>
                <div className={styles.previewWrap}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img alt={`绘本图片 ${page.file.name}`} src={previews[index]?.url} />
                  <span>{page.file.name}</span>
                  <label className={styles.pageNumberField}>
                    <span>这是第</span>
                    <input
                      aria-label={`${page.file.name} 页码`}
                      max={pages.length}
                      min={1}
                      onChange={(event) => updatePageNumber(index, Number(event.target.value))}
                      type="number"
                      value={page.pageNumber}
                    />
                    <span>页</span>
                  </label>
                </div>
                <label>
                  <span>第 {page.pageNumber} 页的故事文字</span>
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
          <strong>页面顺序怎么处理？</strong>
          <span>首次选择图片后，系统仍会按 01、02、03 等文件名自动排序</span>
          <span>如果某张图片排错，直接把“这是第几页”改成正确数字</span>
          <span>页码必须从 1 到总页数且不能重复，保存前系统会自动检查</span>
          <span>真正上传时严格按照人工设置的页码排序，人工页码优先于文件名</span>
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
