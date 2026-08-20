"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ApiClientError,
  type CatalogRelease,
  type Course,
  getAdminCatalog,
  importChineseCatalog,
  listAdminCourses,
} from "@/lib/api/client";

export default function AdminCoursesPage() {
  const [catalog, setCatalog] = useState<CatalogRelease | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [catalogValue, courseValues] = await Promise.all([
        getAdminCatalog(),
        listAdminCourses(),
      ]);
      setCatalog(catalogValue);
      setCourses(courseValues);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "管理数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

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
          <p className="eyebrow">课程与 Catalog</p>
          <h2>系统汉字学习路径</h2>
          <p>系统课程只引用 canonical KnowledgePoint，不建立第二套汉字或掌握度。</p>
        </div>
        <button className="button button-primary" disabled={importing} onClick={() => void runImport()}>
          {importing ? "导入中…" : "受控导入 Catalog"}
        </button>
      </header>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}
      {loading ? <p>加载中…</p> : null}
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
            <p className="eyebrow">System · v{course.version}</p>
            <h3>{course.title}</h3>
            <p>{course.description}</p>
            <div className="course-stat-row">
              <span>{course.units.length} 个阶段</span>
              <span>{course.activity_count} 个活动</span>
              <span>{course.unlearned_count} 个 canonical 知识点</span>
            </div>
            <ol>
              {course.units.map((unit) => <li key={unit.id}>{unit.title}</li>)}
            </ol>
          </article>
        ))}
      </div>
    </section>
  );
}
