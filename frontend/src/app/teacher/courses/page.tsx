"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ChineseCharacter,
  type Course,
  createTeacherCourse,
  listEnabledCharacters,
  listTeacherCourses,
} from "@/lib/api/client";

function TeacherCoursesContent() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [characters, setCharacters] = useState<ChineseCharacter[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [courseValues, page] = await Promise.all([
        listTeacherCourses(),
        listEnabledCharacters(),
      ]);
      setCourses(courseValues);
      setCharacters(page.items);
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "加载失败");
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await createTeacherCourse({
        title,
        description: instructions || null,
        source_type: "teacher",
        units: [
          {
            title: "教师字表",
            activities: [
              {
                title: "按顺序学习",
                activity_type: "character_learning",
                instructions,
                knowledge_points: selected.map((knowledgePointId) => ({
                  knowledge_point_id: knowledgePointId,
                  role: "primary",
                })),
              },
            ],
          },
        ],
      });
      setTitle("");
      setInstructions("");
      setSelected([]);
      setMessage("教师课程已创建。它不会自动授予任何孩子访问权限。");
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="teacher-page section-shell">
      <header className="courses-hero">
        <div><p className="eyebrow">教师模式</p><h1>我的课程与字表</h1></div>
        <Link className="button button-secondary" href="/teacher">返回教师工作台</Link>
      </header>
      <p className="privacy-note">
        教师课程只引用系统 KnowledgePoint；只有家长授权关系有效时，家庭才能为孩子选择。
      </p>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}
      <form className="course-builder" onSubmit={(event) => void submit(event)}>
        <h2>创建教师课程</h2>
        <label>名称<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>教学说明<textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} /></label>
        <fieldset className="choice-field">
          <legend>选择 canonical 汉字</legend>
          <div className="character-choice-grid">
            {characters.map((character) => (
              <label className={selected.includes(character.id) ? "selected" : ""} key={character.id}>
                <input
                  checked={selected.includes(character.id)}
                  onChange={() =>
                    setSelected((values) =>
                      values.includes(character.id)
                        ? values.filter((value) => value !== character.id)
                        : [...values, character.id],
                    )
                  }
                  type="checkbox"
                />
                <strong>{character.character}</strong><small>{character.pinyin}</small>
              </label>
            ))}
          </div>
        </fieldset>
        <button className="button button-primary" disabled={busy || !title || !selected.length}>
          {busy ? "创建中…" : "创建课程"}
        </button>
      </form>
      <section className="course-grid">
        {courses.map((course) => (
          <article className="course-card" key={course.id}>
            <p className="eyebrow">Teacher Course · v{course.version}</p>
            <h2>{course.title}</h2>
            <p>{course.description}</p>
            <span>{course.unlearned_count} 个 canonical 汉字</span>
          </article>
        ))}
      </section>
    </main>
  );
}

export default function TeacherCoursesPage() {
  return <ProtectedPage><TeacherCoursesContent /></ProtectedPage>;
}
