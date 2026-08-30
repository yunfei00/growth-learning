"use client";

import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiClientError,
  type AdminKnowledgePoint,
  type Course,
  type CourseActivity,
  type CurriculumRelease,
  type CurriculumValidationReport,
  type Subject,
  addCurriculumActivity,
  addCurriculumKnowledgePoint,
  addCurriculumLesson,
  addCurriculumUnit,
  cloneCurriculumRelease,
  createCurriculumRelease,
  exportCurriculumRelease,
  getCurriculumRelease,
  listAdminKnowledge,
  listCurriculumReleases,
  moveCurriculumNode,
  previewCurriculumRelease,
  removeCurriculumKnowledgePoint,
  transitionCurriculumRelease,
  updateCurriculumNode,
  validateCurriculumRelease,
} from "@/lib/api/client";

const SUBJECT_LABELS: Record<Subject, string> = {
  chinese: "语文", math: "数学", english: "英语", science: "科学",
};
const STATUS_LABELS: Record<CurriculumRelease["status"], string> = {
  draft: "草稿", in_review: "审核中", published: "已发布", archived: "已归档",
};
const ACTIVITY_LABELS: Record<CourseActivity["activity_type"], string> = {
  knowledge_learning: "知识学习", guided_practice: "引导练习",
  independent_practice: "独立练习", knowledge_review: "知识复习",
  knowledge_check: "知识检查", listening: "听力", speaking: "表达",
  character_learning: "汉字学习", character_review: "汉字复习",
  recognition_check: "识别检查", reading: "阅读",
  science_reference: "科学参考", offline_instruction: "线下活动",
};
const GRADES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] as const;

function gradeLabel(grade: number): string {
  return grade === 0 ? "启蒙" : `${["", "一", "二", "三", "四", "五", "六", "七", "八", "九"][grade]}年级`;
}

function semesterLabel(semester: Course["semester"]): string {
  return semester === "full_year" ? "全年" : semester === "semester_1" ? "上学期" : "下学期";
}

function curriculumKey(grade: number, subject: Subject, semester: Course["semester"]): string {
  if (grade === 0) return `gl:foundation:${subject}:full-year`;
  return `gl:grade${grade}:${subject}:${semester === "semester_1" ? "semester1" : "semester2"}`;
}

function CurriculumBuilder({ release, onChange, onMessage, onError }: {
  release: CurriculumRelease;
  onChange: (value: CurriculumRelease) => void;
  onMessage: (value: string) => void;
  onError: (value: string) => void;
}) {
  const [working, setWorking] = useState("");
  const [pickerActivityId, setPickerActivityId] = useState("");
  const [knowledgeSearch, setKnowledgeSearch] = useState("");
  const [knowledgePoints, setKnowledgePoints] = useState<AdminKnowledgePoint[]>([]);
  const course = release.course;
  const editable = release.status === "draft";

  useEffect(() => {
    if (!pickerActivityId) return;
    const timer = window.setTimeout(() => {
      void listAdminKnowledge({ subject: release.subject, status: "active", search: knowledgeSearch, pageSize: 100 })
        .then((value) => setKnowledgePoints(value.items)).catch(() => setKnowledgePoints([]));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [knowledgeSearch, pickerActivityId, release.subject]);

  const mutate = async (key: string, action: () => Promise<CurriculumRelease>, success: string) => {
    setWorking(key); onError("");
    try { onChange(await action()); onMessage(success); }
    catch (error) { onError(error instanceof ApiClientError ? error.message : "课程结构操作失败"); }
    finally { setWorking(""); }
  };

  if (!course) return null;
  const editNode = (type: "unit" | "lesson" | "activity", id: string, currentTitle: string) => {
    const title = window.prompt("修改标题", currentTitle)?.trim();
    if (title && title !== currentTitle) void mutate(`edit:${id}`, () => updateCurriculumNode(type, id, { title }), "标题已保存。");
  };
  const archiveNode = (type: "unit" | "lesson" | "activity", id: string) => {
    if (window.confirm("归档后不会进入发布结构，确定继续吗？")) void mutate(`archive:${id}`, () => updateCurriculumNode(type, id, { status: "archived" }), "内容已归档。");
  };

  return <section className="curriculum-builder-panel">
    <header><div><p className="eyebrow">Course Builder</p><h3>{release.title}</h3><p>Course → Unit → Lesson → Activity → Canonical KnowledgePoint</p></div><span className={`curriculum-status ${release.status}`}>{STATUS_LABELS[release.status]}</span></header>
    {course.units.filter((unit) => unit.status !== "archived").map((unit, unitIndex, units) => <article className="curriculum-unit-node" key={unit.id}>
      <div className="curriculum-node-header"><div><small>Unit {unitIndex + 1}</small><strong>{unit.title}</strong></div>{editable ? <div className="curriculum-node-actions"><button disabled={unitIndex === 0 || working !== ""} onClick={() => void mutate(`move:${unit.id}`, () => moveCurriculumNode("unit", unit.id, "up"), "Unit 顺序已更新。")} type="button">↑</button><button disabled={unitIndex === units.length - 1 || working !== ""} onClick={() => void mutate(`move:${unit.id}`, () => moveCurriculumNode("unit", unit.id, "down"), "Unit 顺序已更新。")} type="button">↓</button><button onClick={() => editNode("unit", unit.id, unit.title)} type="button">编辑</button><button onClick={() => archiveNode("unit", unit.id)} type="button">归档</button></div> : null}</div>
      <div className="curriculum-lesson-list">
        {unit.lessons.filter((lesson) => lesson.status !== "archived").map((lesson, lessonIndex, lessons) => <section className="curriculum-lesson-node" key={lesson.id}>
          <div className="curriculum-node-header"><div><small>Lesson {lessonIndex + 1}</small><strong>{lesson.title}</strong>{lesson.estimated_minutes ? <span>{lesson.estimated_minutes} 分钟</span> : null}</div>{editable ? <div className="curriculum-node-actions"><button disabled={lessonIndex === 0 || working !== ""} onClick={() => void mutate(`move:${lesson.id}`, () => moveCurriculumNode("lesson", lesson.id, "up"), "Lesson 顺序已更新。")} type="button">↑</button><button disabled={lessonIndex === lessons.length - 1 || working !== ""} onClick={() => void mutate(`move:${lesson.id}`, () => moveCurriculumNode("lesson", lesson.id, "down"), "Lesson 顺序已更新。")} type="button">↓</button><button onClick={() => editNode("lesson", lesson.id, lesson.title)} type="button">编辑</button><button onClick={() => archiveNode("lesson", lesson.id)} type="button">归档</button></div> : null}</div>
          <div className="curriculum-activity-list">
            {lesson.activities.filter((activity) => activity.status !== "archived").map((activity, activityIndex, activities) => <article className="curriculum-activity-node" key={activity.id}>
              <div className="curriculum-node-header"><div><small>Activity {activityIndex + 1} · {ACTIVITY_LABELS[activity.activity_type]}</small><strong>{activity.title}</strong></div>{editable ? <div className="curriculum-node-actions"><button disabled={activityIndex === 0 || working !== ""} onClick={() => void mutate(`move:${activity.id}`, () => moveCurriculumNode("activity", activity.id, "up"), "Activity 顺序已更新。")} type="button">↑</button><button disabled={activityIndex === activities.length - 1 || working !== ""} onClick={() => void mutate(`move:${activity.id}`, () => moveCurriculumNode("activity", activity.id, "down"), "Activity 顺序已更新。")} type="button">↓</button><button onClick={() => editNode("activity", activity.id, activity.title)} type="button">编辑</button><button onClick={() => archiveNode("activity", activity.id)} type="button">归档</button></div> : null}</div>
              <div className="curriculum-mapping-list">
                {activity.points.map((point) => <span key={point.mapping_id}><strong>{point.title}</strong><small>{point.reference_code ?? point.knowledge_type}</small>{editable ? <button aria-label={`移除 ${point.title}`} onClick={() => void mutate(`remove:${point.mapping_id}`, async () => { await removeCurriculumKnowledgePoint(point.mapping_id); return getCurriculumRelease(release.id); }, "KnowledgePoint 关联已移除。")} type="button">×</button> : null}</span>)}
                {editable ? <button className="curriculum-add-inline" onClick={() => setPickerActivityId((value) => value === activity.id ? "" : activity.id)} type="button">+ 选择 KnowledgePoint</button> : null}
              </div>
              {pickerActivityId === activity.id ? <div className="curriculum-knowledge-picker"><label><span>搜索当前学科知识点</span><input onChange={(event) => setKnowledgeSearch(event.target.value)} placeholder="名称或 canonical key" value={knowledgeSearch} /></label><div>{knowledgePoints.map((point) => { const linked = activity.points.some((item) => item.knowledge_point_id === point.id); return <button disabled={linked || working !== ""} key={point.id} onClick={() => void mutate(`point:${point.id}`, () => addCurriculumKnowledgePoint(activity.id, { knowledge_point_id: point.id, role: "primary", reference_code: point.canonical_key }), "KnowledgePoint 已关联。")} type="button"><strong>{point.title}</strong><small>{point.canonical_key}</small><span>{linked ? "已选择" : "添加"}</span></button>; })}</div></div> : null}
            </article>)}
            {editable ? <button className="curriculum-add-node" onClick={() => { const title = window.prompt("Activity 名称，例如：数量观察")?.trim(); if (title) void mutate(`add-activity:${lesson.id}`, () => addCurriculumActivity(lesson.id, { title, activity_type: "knowledge_learning" }), "Activity 已添加。"); }} type="button">+ 添加 Activity</button> : null}
          </div>
        </section>)}
        {editable ? <button className="curriculum-add-node" onClick={() => { const title = window.prompt("Lesson 名称，例如：认识1～5")?.trim(); if (title) void mutate(`add-lesson:${unit.id}`, () => addCurriculumLesson(unit.id, { title }), "Lesson 已添加。"); }} type="button">+ 添加 Lesson</button> : null}
      </div>
    </article>)}
    {editable ? <button className="curriculum-add-node root" onClick={() => { const title = window.prompt("Unit 名称")?.trim(); if (title) void mutate(`add-unit:${release.id}`, () => addCurriculumUnit(release.id, { title }), "Unit 已添加。"); }} type="button">+ 添加 Unit</button> : null}
  </section>;
}

export default function AdminCoursesPage() {
  const [grade, setGrade] = useState(0);
  const [semester, setSemester] = useState<Course["semester"]>("full_year");
  const [subject, setSubject] = useState<Subject>("math");
  const [releases, setReleases] = useState<CurriculumRelease[]>([]);
  const [selected, setSelected] = useState<CurriculumRelease | null>(null);
  const [validation, setValidation] = useState<CurriculumValidationReport | null>(null);
  const [preview, setPreview] = useState<CurriculumRelease | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [releaseVersion, setReleaseVersion] = useState("2026-v1");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const stage: Course["education_stage"] = grade === 0 ? "foundation" : grade <= 6 ? "primary" : "junior_middle";
  const activeSemester = grade === 0 ? "full_year" : semester;

  const fetchReleases = useCallback(() => listCurriculumReleases({ educationStage: stage, gradeLevel: grade || undefined, semester: activeSemester }), [activeSemester, grade, stage]);
  useEffect(() => {
    const timer = window.setTimeout(() => { setLoading(true); void fetchReleases().then((rows) => { setReleases(rows); setError(""); }).catch((requestError) => setError(requestError instanceof ApiClientError ? requestError.message : "课程内容中心加载失败")).finally(() => setLoading(false)); }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchReleases]);
  const subjectReleases = useMemo(() => releases.filter((release) => release.subject === subject), [releases, subject]);
  const run = async (key: string, action: () => Promise<CurriculumRelease>, success: string) => {
    setWorking(key); setError(""); setMessage("");
    try { const result = await action(); setSelected(result.course ? result : await getCurriculumRelease(result.id)); setMessage(success); setValidation(null); setPreview(null); setReleases(await fetchReleases()); }
    catch (requestError) { setError(requestError instanceof ApiClientError ? requestError.message : "操作失败"); }
    finally { setWorking(""); }
  };
  const createDraft = async (event: FormEvent) => {
    event.preventDefault();
    await run("create", () => createCurriculumRelease({ curriculum_key: curriculumKey(grade, subject, activeSemester), release_version: releaseVersion.trim(), education_stage: stage, grade_level: grade || null, semester: activeSemester, subject, title: title.trim(), description: description.trim() || null, source_type: "project_curated", source_name: "Growth Learning", license: "project_owned" }), "课程 Draft 已创建，尚未对孩子发布。");
    setShowCreate(false);
  };
  const openRelease = async (releaseId: string) => { setWorking(`open:${releaseId}`); try { setSelected(await getCurriculumRelease(releaseId)); setValidation(null); setPreview(null); } catch (requestError) { setError(requestError instanceof ApiClientError ? requestError.message : "课程详情加载失败"); } finally { setWorking(""); } };
  const runValidation = async () => { if (!selected) return; setWorking("validate"); try { const report = await validateCurriculumRelease(selected.id); setValidation(report); setMessage(report.valid ? `检查通过，${report.warning_count} 个提醒。` : `发现 ${report.error_count} 个阻塞问题。`); } catch (requestError) { setError(requestError instanceof ApiClientError ? requestError.message : "发布检查失败"); } finally { setWorking(""); } };
  const publish = async () => { if (!selected) return; const report = await validateCurriculumRelease(selected.id); setValidation(report); if (report.error_count) { setError("存在阻塞问题，不能发布。"); return; } const confirmed = report.warning_count === 0 || window.confirm(`还有 ${report.warning_count} 个 warning，确认后继续发布吗？`); if (confirmed) await run("publish", () => transitionCurriculumRelease(selected.id, "publish", report.warning_count > 0), "课程版本已发布并锁定。"); };
  const downloadExport = async () => { if (!selected) return; const document = await exportCurriculumRelease(selected.id); const blob = new Blob([JSON.stringify(document, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const anchor = window.document.createElement("a"); anchor.href = url; anchor.download = `${selected.curriculum_key.replaceAll(":", "-")}-${selected.release_version}.json`; anchor.click(); URL.revokeObjectURL(url); };
  const startCreate = () => { setTitle(`${gradeLabel(grade)}${activeSemester === "full_year" ? "" : ` · ${semesterLabel(activeSemester)}`} · ${SUBJECT_LABELS[subject]}`); setDescription(""); setShowCreate(true); };

  return <section className="admin-page curriculum-center">
    <header className="admin-page-header"><div><p className="eyebrow">Curriculum Platform V1</p><h2>课程内容中心</h2><p>教材路径引用 canonical KnowledgePoint；课程完成与能力掌握继续分开。</p></div><Link className="button button-secondary" href="/admin/knowledge">维护知识点</Link></header>
    {error ? <p className="form-message form-error" role="alert">{error}</p> : null}{message ? <p className="form-message form-success" role="status">{message}</p> : null}
    <nav aria-label="年级" className="curriculum-grade-tabs">{GRADES.map((item) => <button className={grade === item ? "active" : ""} key={item} onClick={() => { setGrade(item); setSemester(item === 0 ? "full_year" : "semester_1"); setSelected(null); setValidation(null); setPreview(null); setShowCreate(false); }} type="button">{gradeLabel(item)}</button>)}</nav>
    {grade > 0 ? <nav aria-label="学期" className="curriculum-semester-tabs">{(["semester_1", "semester_2"] as const).map((item) => <button className={semester === item ? "active" : ""} key={item} onClick={() => { setSemester(item); setSelected(null); setValidation(null); }} type="button">{semesterLabel(item)}</button>)}</nav> : null}
    <section className="curriculum-subject-grid">{(Object.keys(SUBJECT_LABELS) as Subject[]).map((item) => { const rows = releases.filter((release) => release.subject === item); return <button className={subject === item ? "active" : ""} key={item} onClick={() => { setSubject(item); setSelected(null); setValidation(null); }} type="button"><span>{SUBJECT_LABELS[item]}</span><small>{rows.length ? `${rows.length} 个 Release · ${STATUS_LABELS[rows[0].status]}` : "尚未创建"}</small></button>; })}</section>
    <div className="curriculum-context-line"><strong>{gradeLabel(grade)} · {semesterLabel(activeSemester)} · {SUBJECT_LABELS[subject]}</strong><button className="button button-primary" onClick={startCreate} type="button">创建 Draft</button></div>
    {showCreate ? <form className="course-builder curriculum-release-form" onSubmit={(event) => void createDraft(event)}><h3>创建课程版本</h3><label>稳定课程身份<input readOnly value={curriculumKey(grade, subject, activeSemester)} /></label><label>Release 版本<input maxLength={80} onChange={(event) => setReleaseVersion(event.target.value)} required value={releaseVersion} /></label><label>课程名称<input maxLength={160} onChange={(event) => setTitle(event.target.value)} required value={title} /></label><label>说明<textarea maxLength={4000} onChange={(event) => setDescription(event.target.value)} value={description} /></label><div className="admin-actions"><button className="button button-primary" disabled={working === "create"} type="submit">保存 Draft</button><button className="button button-secondary" onClick={() => setShowCreate(false)} type="button">取消</button></div></form> : null}
    {loading ? <p>课程版本加载中…</p> : null}
    <div className="curriculum-release-grid">{subjectReleases.map((release) => <article className={selected?.id === release.id ? "selected" : ""} key={release.id}><div><span className={`curriculum-status ${release.status}`}>{STATUS_LABELS[release.status]}</span><small>{release.source_name}</small></div><h3>{release.title}</h3><p><code>{release.curriculum_key}</code></p><dl><div><dt>Release</dt><dd>{release.release_version}</dd></div><div><dt>Unit</dt><dd>{release.unit_count}</dd></div><div><dt>Lesson</dt><dd>{release.lesson_count}</dd></div><div><dt>知识点</dt><dd>{release.knowledge_point_count}</dd></div></dl><button className="button button-secondary" disabled={working === `open:${release.id}`} onClick={() => void openRelease(release.id)} type="button">{release.status === "published" ? "查看" : "编辑"}</button></article>)}{!loading && subjectReleases.length === 0 ? <p className="empty-note">该位置尚未创建课程。只有点击“创建 Draft”才会写入记录。</p> : null}</div>
    {selected ? <><section className="curriculum-release-toolbar"><div><strong>{selected.release_version}</strong><span>Unit {selected.unit_count} · Lesson {selected.lesson_count} · Activity {selected.activity_count} · KnowledgePoint {selected.knowledge_point_count}</span></div><div><button className="button button-secondary" disabled={working !== ""} onClick={() => void runValidation()} type="button">运行验证</button><button className="button button-secondary" onClick={() => void previewCurriculumRelease(selected.id).then((value) => setPreview(value.release)).catch(() => setError("预览加载失败"))} type="button">预览课程</button><button className="button button-secondary" onClick={() => void downloadExport()} type="button">导出 JSON</button>{selected.status === "draft" ? <button className="button button-primary" onClick={() => void run("submit", () => transitionCurriculumRelease(selected.id, "submit"), "课程已送审，结构现在只读。")} type="button">送审</button> : null}{selected.status === "in_review" && !selected.reviewed_at ? <button className="button button-primary" onClick={() => void run("review", () => transitionCurriculumRelease(selected.id, "review"), "审核已通过，可以执行发布检查。")} type="button">审核通过</button> : null}{selected.status === "in_review" ? <button className="button button-secondary" onClick={() => void run("return", () => transitionCurriculumRelease(selected.id, "return-to-draft"), "已退回 Draft，可以继续编辑。")} type="button">退回 Draft</button> : null}{selected.status === "in_review" && selected.reviewed_at ? <button className="button button-primary" onClick={() => void publish()} type="button">发布 {selected.release_version}</button> : null}{selected.status === "published" ? <button className="button button-secondary" onClick={() => { const version = window.prompt("新 Release 版本，例如 2026-v2")?.trim(); const summary = version ? window.prompt("本次改动摘要")?.trim() : ""; if (version && summary) void run("clone", () => cloneCurriculumRelease(selected.id, version, summary), "新版本 Draft 已复制；孩子 Evidence 未复制。"); }} type="button">创建新版本</button> : null}{selected.status === "published" ? <button className="button button-secondary" onClick={() => { if (window.confirm("归档后停止新 Enrollment，已有历史仍可读。")) void run("archive", () => transitionCurriculumRelease(selected.id, "archive"), "Release 已归档。"); }} type="button">归档</button> : null}</div></section><CurriculumBuilder release={selected} onChange={(value) => { setSelected(value); setValidation(null); setPreview(null); }} onError={setError} onMessage={setMessage} /></> : null}
    {validation ? <section className="curriculum-validation-report"><header><div><p className="eyebrow">发布检查</p><h3>{validation.valid ? "结构检查通过" : "仍有阻塞问题"}</h3></div><div><span className="error">{validation.error_count} errors</span><span className="warning">{validation.warning_count} warnings</span></div></header><div className="curriculum-check-grid">{Object.entries(validation.checks).map(([key, ok]) => <span className={ok ? "ok" : "failed"} key={key}>{ok ? "✓" : "✗"} {key}</span>)}</div><ul>{validation.issues.map((issue, index) => <li className={issue.severity} key={`${issue.code}:${issue.path}:${index}`}><strong>{issue.severity === "error" ? "✗" : "⚠"} {issue.message}</strong><code>{issue.path} · {issue.code}</code></li>)}</ul></section> : null}
    {preview?.course ? <section className="curriculum-preview"><header><div><p className="eyebrow">Draft Preview · 无学习写入</p><h3>{preview.title}</h3></div><button className="button button-secondary" onClick={() => setPreview(null)} type="button">关闭预览</button></header>{preview.course.units.map((unit) => <article key={unit.id}><h4>{unit.title}</h4>{unit.lessons.map((lesson) => <div key={lesson.id}><strong>{lesson.title}</strong><ol>{lesson.activities.map((activity) => <li key={activity.id}>{activity.title}<span>{activity.points.map((point) => point.title).join(" · ") || "尚未关联知识点"}</span></li>)}</ol></div>)}</article>)}</section> : null}
  </section>;
}
