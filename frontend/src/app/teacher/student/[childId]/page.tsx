"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type TeacherObservation,
  type TeacherStudent,
  addTeacherObservation,
  getTeacherStudent,
} from "@/lib/api/client";

const CATEGORY_LABELS: Record<TeacherObservation["category"], string> = {
  recognition: "认字表现",
  reading: "阅读",
  expression: "表达",
  learning_habit: "学习习惯",
  participation: "参与情况",
  other: "其他教学观察",
};

function StudentContent({ childId }: { childId: string }) {
  const [student, setStudent] = useState<TeacherStudent | null>(null);
  const [category, setCategory] = useState<TeacherObservation["category"]>("recognition");
  const [text, setText] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setStudent(await getTeacherStudent(childId));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "无法打开学生教学视图");
    }
  }, [childId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const saveObservation = async () => {
    if (!text.trim()) return;
    setWorking(true);
    setError("");
    try {
      await addTeacherObservation(childId, {
        category,
        original_text: text,
        occurred_at: new Date().toISOString(),
      });
      setText("");
      setMessage("教学观察已按原文保存，家长可在成长档案中看到。它不会直接修改掌握度。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "教学观察保存失败");
    } finally {
      setWorking(false);
    }
  };

  if (!student) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>{error || "正在加载有限教学信息…"}</p><Link href="/teacher">返回教师工作台</Link></section>;
  }

  return (
    <section className="teacher-page section-shell">
      <div className="teacher-hero teacher-hero-row">
        <div><p className="eyebrow">学生教学视图</p><h1>{student.nickname || student.display_name}</h1><p>{student.age_band} · 只展示你布置任务所需的汉字状态与教学记录。</p></div>
        <Link className="button button-secondary" href="/teacher">返回工作台</Link>
      </div>
      <div className="privacy-boundary"><strong>隐私边界</strong><span>这里不包含家庭成员、兄弟姐妹、家庭成长记录、科学媒体、故事书、报告或导出。</span></div>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}

      <section className="teacher-panel">
        <p className="eyebrow">任务范围汉字</p><h2>相关掌握状态</h2>
        <div className="mastery-chip-grid">
          {student.relevant_mastery.map((item) => <article key={item.knowledge_point_id}><strong>{item.character}</strong><span>{item.pinyin}</span><small>{item.mastery_level}</small></article>)}
          {student.relevant_mastery.length === 0 ? <p className="empty-note">尚无任务相关汉字。</p> : null}
        </div>
        <p className="privacy-note">掌握状态由统一证据算法生成，老师不能手工把某个字改成“已掌握”。</p>
      </section>

      <section className="teacher-panel">
        <p className="eyebrow">任务</p><h2>完成情况</h2>
        <div className="teacher-assignment-list">
          {student.assignments.map((assignment) => <article key={assignment.assignment_id}><div><strong>{assignment.title}</strong><span>{assignment.progress_status} · {assignment.completed_item_count}/{assignment.total_item_count}</span></div><p>{assignment.instructions}</p><div className="inline-actions"><Link href={`/teacher-tasks/${assignment.assignment_id}/${student.child_id}`}>打开/继续任务</Link><Link href={`/teacher/assignment/${assignment.assignment_id}`}>查看任务统计</Link></div></article>)}
          {student.assignments.length === 0 ? <p className="empty-note">暂无已发布任务。</p> : null}
        </div>
      </section>

      <section className="teacher-panel">
        <p className="eyebrow">教学观察</p><h2>保留老师原话</h2>
        <div className="observation-form"><label>分类<select value={category} onChange={(event) => setCategory(event.target.value as TeacherObservation["category"])}>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>观察原文<textarea placeholder="记录具体发生了什么，不使用分数或永久能力标签。" value={text} onChange={(event) => setText(event.target.value)} /></label><button className="button button-primary" disabled={working || !text.trim()} onClick={() => void saveObservation()} type="button">{working ? "保存中…" : "保存教学观察"}</button></div>
        <div className="observation-list">{student.observations.map((item) => <article key={item.id}><div><strong>{CATEGORY_LABELS[item.category]}</strong><time>{new Date(item.occurred_at).toLocaleString("zh-CN")}</time></div><p>{item.original_text}</p></article>)}</div>
      </section>
    </section>
  );
}

export default function TeacherStudentPage({ params }: { params: { childId: string } }) {
  return <ProtectedPage><StudentContent childId={params.childId} /></ProtectedPage>;
}
