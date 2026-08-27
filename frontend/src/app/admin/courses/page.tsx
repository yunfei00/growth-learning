"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  ApiClientError,
  type AdminKnowledgePoint,
  type CatalogRelease,
  type Course,
  createAdminCourse,
  getAdminCatalog,
  importChineseCatalog,
  listAdminCourses,
  listAdminKnowledge,
  type Subject,
} from "@/lib/api/client";

const SUBJECT_LABELS: Record<Subject, string> = {
  chinese: "语文",
  math: "数学",
  english: "英语",
  science: "科学",
};

export default function AdminCoursesPage() {
  const [catalog, setCatalog] = useState<CatalogRelease | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [subject, setSubject] = useState<Subject | "">("");
  const [showCreate, setShowCreate] = useState(false);
  const [createSubject, setCreateSubject] = useState<Subject>("math");
  const [availablePoints, setAvailablePoints] = useState<AdminKnowledgePoint[]>([]);
  const [selectedPointIds, setSelectedPointIds] = useState<string[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [catalogValue, courseValues] = await Promise.all([
        getAdminCatalog(),
        listAdminCourses(subject || undefined),
      ]);
      setCatalog(catalogValue);
      setCourses(courseValues);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "管理数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [subject]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!showCreate) return;
    const timer = window.setTimeout(() => {
      listAdminKnowledge({ subject: createSubject, status: "active", pageSize: 100 })
        .then((value) => setAvailablePoints(value.items))
        .catch(() => setAvailablePoints([]));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [createSubject, showCreate]);

  const submitCourse = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedPointIds.length) return;
    setSaving(true);
    setError("");
    try {
      await createAdminCourse({
        subject: createSubject,
        title: title.trim(),
        description: description.trim() || null,
        source_type: "system",
        units: [{
          title: "基础单元",
          activities: [{
            title: "知识学习",
            activity_type: "knowledge_learning",
            knowledge_points: selectedPointIds.map((knowledgePointId) => ({
              knowledge_point_id: knowledgePointId,
              role: "primary",
            })),
          }],
        }],
      });
      setMessage("系统课程已创建；课程完成仍不等于掌握。 ");
      setTitle("");
      setDescription("");
      setSelectedPointIds([]);
      setShowCreate(false);
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "课程创建失败");
    } finally {
      setSaving(false);
    }
  };

  const runImport = async () => {
    setImporting(true);
    setMessage("");
    try {
      const report = await importChineseCatalog();
      if (report.errors.length) throw new Error("Catalog import returned errors");
      setMessage(
        `导入完成：新增 ${report.created}，更新 ${report.updated}，保留 ${report.preserved}，当前 ${report.catalog_size} 字。`,
      );
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "导入失败");
    } finally {
      setImporting(false);
    }
  };

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="eyebrow">Courses · Canonical knowledge</p>
          <h2>系统课程</h2>
          <p>按学科组织课程；课程只引用 canonical KnowledgePoint，不建立第二套掌握度。</p>
        </div>
        <div className="admin-actions">
          <button className="button button-secondary" disabled={importing} onClick={() => void runImport()}>{importing ? "导入中…" : "受控导入汉字 Catalog"}</button>
          <button className="button button-primary" onClick={() => setShowCreate((value) => !value)}>{showCreate ? "收起" : "创建系统课程"}</button>
        </div>
      </header>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}
      {loading ? <p>加载中…</p> : null}
      <div className="admin-filter-bar">
        <label><span>学科</span><select value={subject} onChange={(event) => setSubject(event.target.value as Subject | "")}><option value="">全部学科</option>{(Object.keys(SUBJECT_LABELS) as Subject[]).map((item) => <option value={item} key={item}>{SUBJECT_LABELS[item]}</option>)}</select></label>
      </div>
      {showCreate ? <form className="course-builder" onSubmit={(event) => void submitCourse(event)}>
        <h3>新建系统课程</h3>
        <label>学科<select value={createSubject} onChange={(event) => { setCreateSubject(event.target.value as Subject); setSelectedPointIds([]); }}><option value="chinese">语文</option><option value="math">数学</option><option value="english">英语</option><option value="science">科学</option></select></label>
        <label>课程名称<input required value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>简介<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <fieldset className="choice-field"><legend>选择该学科的知识点</legend><div className="character-choice-grid">{availablePoints.map((point) => <label className={selectedPointIds.includes(point.id) ? "selected" : ""} key={point.id}><input type="checkbox" checked={selectedPointIds.includes(point.id)} onChange={() => setSelectedPointIds((items) => items.includes(point.id) ? items.filter((id) => id !== point.id) : [...items, point.id])} /><strong>{point.title}</strong><small>{point.canonical_key}</small></label>)}</div>{availablePoints.length === 0 ? <p className="empty-note">该学科暂无知识点。请先在“知识点”页面人工维护，系统不会创建假内容。</p> : null}</fieldset>
        <button className="button button-primary" disabled={saving || !selectedPointIds.length}>{saving ? "创建中…" : "创建课程"}</button>
      </form> : null}
      {catalog ? (
        <article className="catalog-provenance-card">
          <div><span>Catalog Version</span><strong>{catalog.catalog_version}</strong></div>
          <div><span>字数</span><strong>{catalog.item_count}</strong></div>
          <div><span>来源</span><strong>{catalog.source_name}</strong></div>
          <div><span>许可</span><strong>{catalog.license || "未标注"}</strong></div>
          <p>{catalog.metadata.notice}</p>
          {catalog.source_reference ? (
            <a href={catalog.source_reference} rel="noreferrer" target="_blank">查看数据来源</a>
          ) : null}
        </article>
      ) : null}
      <div className="course-unit-list">
        {courses.map((course) => (
          <article className="course-card" key={course.id}>
            <p className="eyebrow">{SUBJECT_LABELS[course.subject]} · System · v{course.version}</p>
            <h3>{course.title}</h3>
            <p>{course.description}</p>
            <div className="course-stat-row">
              <span>{course.units.length} 个阶段</span>
              <span>{course.activity_count} 个活动</span>
              <span>{course.projection_unavailable_count ? `${course.projection_unavailable_count} 项掌握度未配置` : `${course.unlearned_count} 项未学习`}</span>
            </div>
            <ol>
              {course.units.map((unit) => <li key={unit.id}>{unit.title}</li>)}
            </ol>
          </article>
        ))}
      </div>
      {!loading && courses.length === 0 ? <p className="empty-note">当前学科暂无系统课程；生产环境没有自动填充演示内容。</p> : null}
    </section>
  );
}
