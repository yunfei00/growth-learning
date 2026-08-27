"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ChineseCharacter,
  type Course,
  type Subject,
  copyCoursePath,
  createFamilyCourse,
  enrollCourse,
  listCourses,
  listEnabledCharacters,
  updateCourseEnrollment,
} from "@/lib/api/client";

const sourceLabels: Record<Course["source_type"], string> = {
  system: "系统课程",
  family: "家庭课程",
  teacher: "老师课程",
  textbook_reference: "教材参考",
};

const subjectLabels: Record<Subject, string> = {
  chinese: "语文",
  math: "数学",
  english: "英语",
  science: "科学",
};

function CoursesContent() {
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [courses, setCourses] = useState<Course[]>([]);
  const [subject, setSubject] = useState<Subject | "">("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [sourceType, setSourceType] = useState<"family" | "textbook_reference">("family");
  const [referenceName, setReferenceName] = useState("");
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<ChineseCharacter[]>([]);
  const [selected, setSelected] = useState<ChineseCharacter[]>([]);
  const [copyTarget, setCopyTarget] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setCourses(await listCourses(activeChild.id, subject || undefined));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "课程加载失败");
    }
  }, [activeChild, subject]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!showCreate) return;
    const timer = window.setTimeout(() => {
      listEnabledCharacters(search)
        .then((page) => setSearchResults(page.items.slice(0, 24)))
        .catch(() => setSearchResults([]));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [search, showCreate]);

  const changeEnrollment = async (course: Course) => {
    if (!activeChild) return;
    setBusy(course.id);
    setMessage("");
    try {
      if (!course.enrollment_id) {
        await enrollCourse(activeChild.id, course.id, courses.filter((item) => item.enrollment_id).length);
      } else {
        await updateCourseEnrollment(
          activeChild.id,
          course.enrollment_id,
          course.enrollment_status === "active" ? "paused" : "active",
        );
      }
      setMessage("学习路径已更新。");
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "无法更新课程");
    } finally {
      setBusy("");
    }
  };

  const submitCourse = async (event: FormEvent) => {
    event.preventDefault();
    if (!family || selected.length === 0) return;
    setBusy("create");
    try {
      await createFamilyCourse(family.id, {
        title,
        description: description || null,
        source_type: sourceType,
        reference_metadata:
          sourceType === "textbook_reference" ? { reference_name: referenceName } : {},
        units: [
          {
            title: "自定义字表",
            activities: [
              {
                title: "按顺序学习",
                activity_type: "character_learning",
                knowledge_points: selected.map((character) => ({
                  knowledge_point_id: character.id,
                  role: "primary",
                })),
              },
            ],
          },
        ],
      });
      setTitle("");
      setDescription("");
      setSelected([]);
      setShowCreate(false);
      setMessage("家庭课程已创建，可加入当前孩子的学习路径。");
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "课程创建失败");
    } finally {
      setBusy("");
    }
  };

  const copyPath = async () => {
    if (!activeChild || !copyTarget) return;
    setBusy("copy");
    try {
      const result = await copyCoursePath(activeChild.id, copyTarget);
      setMessage(
        `已复制 ${result.copied_enrollments} 条课程选择；掌握度和学习历史没有复制。`,
      );
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "复制失败");
    } finally {
      setBusy("");
    }
  };

  if (status !== "ready" || !family || !activeChild) {
    return <section className="center-state section-shell">正在加载学习路径…</section>;
  }

  return (
    <main className="courses-page section-shell">
      <header className="courses-hero">
        <div>
          <p className="eyebrow">学习路径</p>
          <h1>课程</h1>
          <p>课程决定新字优先顺序；复习积压与每日容量仍由自适应算法决定。</p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={setActiveChildId}
        />
      </header>

      <aside className="course-principle" role="note">
        <strong>课程完成 ≠ 知识掌握</strong>
        <span>课程进度只统计活动完成；认识和稳定掌握来自真实学习与检测证据。</span>
      </aside>

      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}

      <section className="course-actions">
        <label>
          学科
          <select value={subject} onChange={(event) => setSubject(event.target.value as Subject | "")}>
            <option value="">全部学科</option>
            {(Object.keys(subjectLabels) as Subject[]).map((item) => <option key={item} value={item}>{subjectLabels[item]}</option>)}
          </select>
        </label>
        {family.current_role === "admin" ? (
          <button className="button button-primary" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "收起" : "创建家庭课程"}
          </button>
        ) : null}
        {family.current_role === "admin" && children.length > 1 ? (
          <div className="copy-path-control">
            <select
              aria-label="复制学习路径给另一个孩子"
              value={copyTarget}
              onChange={(event) => setCopyTarget(event.target.value)}
            >
              <option value="">复制路径给…</option>
              {children
                .filter((child) => child.id !== activeChild.id)
                .map((child) => (
                  <option key={child.id} value={child.id}>
                    {child.nickname || child.display_name}
                  </option>
                ))}
            </select>
            <button disabled={!copyTarget || busy === "copy"} onClick={() => void copyPath()}>
              {busy === "copy" ? "复制中…" : "确认复制"}
            </button>
          </div>
        ) : null}
      </section>

      {showCreate ? (
        <form className="course-builder" onSubmit={(event) => void submitCourse(event)}>
          <h2>新建家庭课程</h2>
          <label>
            课程类型
            <select
              value={sourceType}
              onChange={(event) =>
                setSourceType(event.target.value as "family" | "textbook_reference")
              }
            >
              <option value="family">家庭主题课程</option>
              <option value="textbook_reference">教材参考课程</option>
            </select>
          </label>
          <label>
            课程名称
            <input required value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          {sourceType === "textbook_reference" ? (
            <label>
              参考名称（只保存名称，不复制教材内容）
              <input
                required
                value={referenceName}
                onChange={(event) => setReferenceName(event.target.value)}
              />
            </label>
          ) : null}
          <label>
            简介
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label>
            搜索并选择系统汉字
            <input value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
          <div className="character-pick-grid">
            {searchResults.map((character) => {
              const active = selected.some((item) => item.id === character.id);
              return (
                <button
                  className={active ? "selected" : ""}
                  key={character.id}
                  onClick={() =>
                    setSelected((items) =>
                      active
                        ? items.filter((item) => item.id !== character.id)
                        : [...items, character],
                    )
                  }
                  type="button"
                >
                  {character.character}
                </button>
              );
            })}
          </div>
          <p>已选：{selected.map((item) => item.character).join("、") || "尚未选择"}</p>
          <button className="button button-primary" disabled={!title || !selected.length || busy === "create"}>
            {busy === "create" ? "创建中…" : "创建课程"}
          </button>
        </form>
      ) : null}

      <section className="course-grid">
        {courses.map((course) => (
          <article className="course-card" key={course.id}>
            <div className="course-card-topline">
              <span>{subjectLabels[course.subject]} · {sourceLabels[course.source_type]}</span>
              <span>{course.enrollment_status ? `路径：${course.enrollment_status}` : "未选择"}</span>
            </div>
            <h2>{course.title}</h2>
            <p>{course.description}</p>
            <div className="course-stat-row">
              <span>课程完成 {course.completed_activities}/{course.activity_count}</span>
              {course.projection_unavailable_count ? (
                <span>{course.projection_unavailable_count} 项掌握度策略未配置</span>
              ) : (
                <><span>已学习 {course.introduced_count}</span><span>稳定掌握 {course.stable_count}</span><span>待学习 {course.unlearned_count}</span></>
              )}
            </div>
            <div className="course-card-actions">
              <Link href={`/courses/${course.id}`}>查看详情</Link>
              {family.current_role === "admin" ? (
                <button disabled={busy === course.id} onClick={() => void changeEnrollment(course)}>
                  {!course.enrollment_id
                    ? "加入路径"
                    : course.enrollment_status === "active"
                      ? "暂停"
                      : "继续"}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </section>
      {courses.length === 0 ? <p className="empty-note">当前学科暂无可用课程。</p> : null}
    </main>
  );
}

export default function CoursesPage() {
  return (
    <ProtectedPage>
      <CoursesContent />
    </ProtectedPage>
  );
}
