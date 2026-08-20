"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ChineseCharacter,
  type TeacherAssignmentType,
  type TeacherDashboard,
  createTeacherAssignment,
  createTeacherClassroom,
  enableTeacherMode,
  getTeacherDashboard,
  listEnabledCharacters,
  publishTeacherAssignment,
  rotateTeacherCode,
} from "@/lib/api/client";

const TYPE_LABELS: Record<TeacherAssignmentType, string> = {
  character_learning: "识字学习",
  character_review: "识字复习",
  recognition_check: "认字小检测",
  reading: "阅读任务",
  freeform_instruction: "线下任务说明",
};

function TeacherPageContent() {
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState<TeacherDashboard | null>(null);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [characters, setCharacters] = useState<ChineseCharacter[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [profileName, setProfileName] = useState(user?.display_name ?? "");
  const [organization, setOrganization] = useState("");
  const [className, setClassName] = useState("");
  const [classDescription, setClassDescription] = useState("");
  const [assignmentType, setAssignmentType] =
    useState<TeacherAssignmentType>("recognition_check");
  const [assignmentTitle, setAssignmentTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [classroomId, setClassroomId] = useState("");
  const [targetIds, setTargetIds] = useState<string[]>([]);
  const [pointIds, setPointIds] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      const value = await getTeacherDashboard();
      setDashboard(value);
      setNeedsProfile(false);
      setError("");
      const catalog = await listEnabledCharacters();
      setCharacters(catalog.items);
    } catch (reason) {
      if (reason instanceof ApiClientError && reason.status === 403) {
        setNeedsProfile(true);
      } else {
        setError(reason instanceof ApiClientError ? reason.message : "教师工作台加载失败");
      }
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const createProfile = async () => {
    if (!profileName.trim()) return;
    setWorking(true);
    setError("");
    try {
      await enableTeacherMode({
        display_name: profileName.trim(),
        organization_name: organization.trim() || null,
      });
      setMessage("教师模式已开启。创建资料不会自动获得任何孩子权限。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "无法开启教师模式");
    } finally {
      setWorking(false);
    }
  };

  const createClass = async () => {
    if (!className.trim()) return;
    setWorking(true);
    setError("");
    try {
      await createTeacherClassroom({
        name: className.trim(),
        description: classDescription.trim() || null,
      });
      setClassName("");
      setClassDescription("");
      setMessage("班级已创建。孩子仍需家长输入班级码并明确确认加入。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "无法创建班级");
    } finally {
      setWorking(false);
    }
  };

  const createAssignment = async () => {
    if (!assignmentTitle.trim() || !instructions.trim() || targetIds.length === 0) return;
    const needsCharacters = [
      "character_learning",
      "character_review",
      "recognition_check",
    ].includes(assignmentType);
    if (needsCharacters && pointIds.length === 0) return;
    setWorking(true);
    setError("");
    try {
      const assignment = await createTeacherAssignment({
        classroom_id: classroomId || null,
        title: assignmentTitle.trim(),
        instructions: instructions.trim(),
        assignment_type: assignmentType,
        due_at: dueAt ? new Date(dueAt).toISOString() : null,
        target_child_ids: targetIds,
        knowledge_point_ids: needsCharacters ? pointIds : [],
      });
      await publishTeacherAssignment(assignment.id);
      setAssignmentTitle("");
      setInstructions("");
      setDueAt("");
      setPointIds([]);
      setMessage("任务已发布，家庭端会在独立的“老师任务”区域看到它。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "任务发布失败");
    } finally {
      setWorking(false);
    }
  };

  if (needsProfile) {
    return (
      <section className="teacher-page section-shell">
        <div className="teacher-hero">
          <p className="eyebrow">教师模式</p>
          <h1>开启有限的教师协作</h1>
          <p>
            这不是教师认证，也不会自动看到任何孩子。只有家长管理员使用教师码明确授权后，
            才能看到该孩子的有限教学信息。
          </p>
        </div>
        <div className="teacher-form-card narrow-card">
          <label>老师显示名<input value={profileName} onChange={(event) => setProfileName(event.target.value)} /></label>
          <label>机构/小组（可选）<input value={organization} onChange={(event) => setOrganization(event.target.value)} /></label>
          {error ? <p className="form-message form-error">{error}</p> : null}
          <button className="button button-primary" disabled={working} onClick={() => void createProfile()} type="button">
            {working ? "正在开启…" : "开启教师模式"}
          </button>
        </div>
      </section>
    );
  }

  if (!dashboard) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>{error || "正在加载教师工作台…"}</p></section>;
  }

  const toggle = (value: string, values: string[], setter: (next: string[]) => void) => {
    setter(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  return (
    <section className="teacher-page section-shell">
      <div className="teacher-hero teacher-hero-row">
        <div><p className="eyebrow">教师模式</p><h1>{dashboard.profile.display_name}的教学工作台</h1><p>只显示家长明确授权的孩子和你自己布置的教学证据。</p></div>
        <Link className="button button-secondary" href="/home">切换到家长模式</Link>
      </div>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}

      <div className="teacher-metric-grid">
        <article><span>我的班级</span><strong>{dashboard.classrooms.filter((item) => item.status === "active").length}</strong></article>
        <article><span>我的学生</span><strong>{dashboard.students.length}</strong></article>
        <article><span>已发布任务</span><strong>{dashboard.assignments.filter((item) => item.status === "published").length}</strong></article>
        <article><span>最近完成</span><strong>{dashboard.recent_completed_count}</strong></article>
      </div>

      <div className="teacher-two-column">
        <section className="teacher-panel">
          <div className="section-title-row"><div><p className="eyebrow">Share code</p><h2>教师码</h2></div></div>
          <code className="share-code">{dashboard.profile.teacher_code}</code>
          <p className="privacy-note">只分享给需要协作的家长。输入代码只展示最少资料，仍需家长确认具体孩子。</p>
          <button className="text-button" disabled={working} onClick={() => void (async () => { setWorking(true); try { await rotateTeacherCode(); setMessage("教师码已轮换，旧码立即失效。"); await load(); } finally { setWorking(false); } })()} type="button">轮换教师码</button>
        </section>
        <section className="teacher-panel">
          <p className="eyebrow">Classroom V1</p><h2>创建轻量班级</h2>
          <label>班级名称<input placeholder="大一班识字小组" value={className} onChange={(event) => setClassName(event.target.value)} /></label>
          <label>简短说明<input value={classDescription} onChange={(event) => setClassDescription(event.target.value)} /></label>
          <button className="button button-secondary" disabled={working || !className.trim()} onClick={() => void createClass()} type="button">创建班级</button>
        </section>
      </div>

      <section className="teacher-panel">
        <div className="section-title-row"><div><p className="eyebrow">我的班级</p><h2>家长确认加入的教学小组</h2></div></div>
        <div className="teacher-card-grid">
          {dashboard.classrooms.map((classroom) => <article className="teacher-list-card" key={classroom.id}><div><strong>{classroom.name}</strong><span>{classroom.status === "active" ? "进行中" : "已归档"}</span></div><p>{classroom.description || "暂无说明"}</p><small>{classroom.student_count} 名已授权学生</small><code>{classroom.class_code}</code></article>)}
          {dashboard.classrooms.length === 0 ? <p className="empty-note">尚未创建班级。</p> : null}
        </div>
      </section>

      <section className="teacher-panel">
        <div className="section-title-row"><div><p className="eyebrow">我的学生</p><h2>仅限有效家长授权</h2></div></div>
        <div className="teacher-card-grid">
          {dashboard.students.map((student) => <Link className="teacher-list-card" href={`/teacher/student/${student.child_id}`} key={student.child_id}><div><strong>{student.nickname || student.display_name}</strong><span>{student.age_band}</span></div><p>{student.assignments.length} 个教学任务 · {student.observations.length} 条观察</p><small>打开有限教学视图 →</small></Link>)}
          {dashboard.students.length === 0 ? <p className="empty-note">暂无授权学生。请把教师码或班级码交给家长确认。</p> : null}
        </div>
      </section>

      <section className="teacher-panel assignment-builder">
        <p className="eyebrow">新建任务</p><h2>布置一个小而清晰的任务</h2>
        <div className="teacher-form-grid">
          <label>任务类型<select value={assignmentType} onChange={(event) => setAssignmentType(event.target.value as TeacherAssignmentType)}>{Object.entries(TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>班级（可选）<select value={classroomId} onChange={(event) => setClassroomId(event.target.value)}><option value="">不限定班级</option>{dashboard.classrooms.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>标题<input value={assignmentTitle} onChange={(event) => setAssignmentTitle(event.target.value)} /></label>
          <label>截止时间（可选）<input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} /></label>
          <label className="full-field">任务说明<textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} /></label>
        </div>
        <fieldset className="choice-field"><legend>选择已授权孩子</legend><div>{dashboard.students.map((student) => <label key={student.child_id}><input checked={targetIds.includes(student.child_id)} onChange={() => toggle(student.child_id, targetIds, setTargetIds)} type="checkbox" />{student.nickname || student.display_name}</label>)}</div></fieldset>
        {["character_learning", "character_review", "recognition_check"].includes(assignmentType) ? <fieldset className="choice-field"><legend>选择系统汉字知识点（1–50）</legend><div className="character-choice-grid">{characters.map((character) => <label className={pointIds.includes(character.id) ? "selected" : ""} key={character.id}><input checked={pointIds.includes(character.id)} onChange={() => toggle(character.id, pointIds, setPointIds)} type="checkbox" /><strong>{character.character}</strong><small>{character.pinyin}</small></label>)}</div></fieldset> : <p className="privacy-note">阅读任务会引导家庭进入现有故事书流程，不会绕过掌握快照、覆盖率分析或内容安全。</p>}
        <button className="button button-primary" disabled={working || targetIds.length === 0 || !assignmentTitle.trim() || !instructions.trim()} onClick={() => void createAssignment()} type="button">创建并发布</button>
      </section>

      <section className="teacher-panel">
        <div className="section-title-row"><div><p className="eyebrow">任务结果</p><h2>只看自己任务范围</h2></div></div>
        <div className="teacher-assignment-list">{dashboard.assignments.map((assignment) => <article key={assignment.id}><div><strong>{assignment.title}</strong><span>{TYPE_LABELS[assignment.assignment_type]} · {assignment.status}</span></div><p>{assignment.instructions}</p><div className="assignment-target-row">{assignment.targets.map((target) => <span key={target.child_id}>{target.child_name}：{target.progress_status} {target.completed_item_count}/{target.total_item_count}</span>)}</div>{assignment.status === "published" ? <div className="inline-actions"><Link href={`/teacher/assignment/${assignment.id}`}>查看统计</Link>{assignment.targets.map((target) => <Link href={`/teacher-tasks/${assignment.id}/${target.child_id}`} key={target.child_id}>现场执行：{target.child_name}</Link>)}</div> : null}</article>)}</div>
      </section>
    </section>
  );
}

export default function TeacherPage() {
  return <ProtectedPage><TeacherPageContent /></ProtectedPage>;
}
