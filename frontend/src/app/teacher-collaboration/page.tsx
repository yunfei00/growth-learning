"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ParentTeacherCollaboration,
  type TeacherClassroom,
  type TeacherPublicProfile,
  connectChildTeacher,
  getParentTeacherCollaboration,
  leaveTeacherClassroom,
  resolveTeacherConnection,
  revokeChildTeacher,
} from "@/lib/api/client";

function CollaborationContent() {
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [data, setData] = useState<ParentTeacherCollaboration | null>(null);
  const [code, setCode] = useState("");
  const [resolved, setResolved] = useState<{
    kind: "teacher" | "classroom";
    teacher: TeacherPublicProfile;
    classroom: TeacherClassroom | null;
  } | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setData(await getParentTeacherCollaboration(activeChild.id));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "老师协作信息加载失败");
    }
  }, [activeChild]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const lookup = async () => {
    if (!code.trim()) return;
    setWorking(true);
    setError("");
    setResolved(null);
    try {
      setResolved(await resolveTeacherConnection(code.trim()));
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "没有找到这个连接码");
    } finally {
      setWorking(false);
    }
  };

  const confirm = async () => {
    if (!activeChild || !resolved) return;
    setWorking(true);
    setError("");
    try {
      await connectChildTeacher(activeChild.id, code.trim());
      setMessage(
        resolved.kind === "classroom"
          ? "已明确授权老师并让当前孩子加入班级。"
          : "已明确授权该老师访问当前孩子的有限教学信息。",
      );
      setCode("");
      setResolved(null);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "授权失败");
    } finally {
      setWorking(false);
    }
  };

  if (status !== "ready") {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在加载家庭权限…</p></section>;
  }
  if (!family || !activeChild) {
    return <section className="center-state section-shell"><h1>老师协作属于家庭模式</h1><p>请先创建家庭和孩子，或切换到教师工作台。</p><Link href="/teacher">进入教师模式</Link></section>;
  }

  const isAdmin = family.current_role === "admin";
  return (
    <section className="teacher-page section-shell">
      <div className="teacher-hero teacher-hero-row"><div><p className="eyebrow">家长模式 · 老师协作</p><h1>由家长决定谁能参与教学</h1><p>授权只针对当前选择的孩子，不会自动覆盖兄弟姐妹，也不会让老师成为家庭成员。</p></div><ChildSwitcher activeChildId={activeChild.id} childOptions={children} onChange={setActiveChildId} /></div>
      <div className="privacy-boundary"><strong>当前权限：{isAdmin ? "家庭管理员" : "陪伴者"}</strong><span>{isAdmin ? "可以连接、加入和撤销老师。" : "可以陪孩子完成任务，但不能修改老师授权。"}</span></div>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}

      {isAdmin ? <section className="teacher-panel connection-panel"><p className="eyebrow">连接老师或班级</p><h2>输入不透明连接码</h2><div className="inline-form"><input aria-label="教师码或班级码" autoComplete="off" placeholder="教师码或班级码" value={code} onChange={(event) => { setCode(event.target.value); setResolved(null); }} /><button className="button button-secondary" disabled={working || !code.trim()} onClick={() => void lookup()} type="button">查询</button></div>{resolved ? <article className="connection-confirm"><div><strong>{resolved.teacher.display_name}</strong><span>{resolved.teacher.organization_name || "未填写机构"}</span></div>{resolved.classroom ? <p>班级：{resolved.classroom.name}</p> : <p>老师身份资料（未进行职业资质认证）</p>}<p>{resolved.teacher.short_bio || "暂无简介"}</p><button className="button button-primary" disabled={working} onClick={() => void confirm()} type="button">确认授权给 {activeChild.nickname || activeChild.display_name}</button></article> : null}<p className="privacy-note">查询连接码不会授权；必须点击确认。系统不提供按邮箱搜索老师。</p></section> : null}

      <section className="teacher-panel">
        <p className="eyebrow">老师</p><h2>当前孩子的授权记录</h2>
        <div className="teacher-assignment-list">{data?.relations.map((relation) => <article key={relation.id}><div><strong>{relation.teacher.display_name}</strong><span>{relation.status === "active" ? "授权中" : "已撤销"}</span></div><p>{relation.teacher.organization_name || "未填写机构"} · 权限版本 {relation.permission_version}</p>{isAdmin && relation.status === "active" ? <button className="danger-text-button" disabled={working} onClick={() => void (async () => { setWorking(true); try { await revokeChildTeacher(activeChild.id, relation.id); setMessage("老师权限已立即撤销；历史任务和证据仍为家庭保留。"); await load(); } catch (reason) { setError(reason instanceof ApiClientError ? reason.message : "撤销失败"); } finally { setWorking(false); } })()} type="button">撤销老师授权</button> : null}</article>)}{data?.relations.length === 0 ? <p className="empty-note">当前孩子尚未授权老师。</p> : null}</div>
      </section>

      <section className="teacher-panel">
        <p className="eyebrow">班级</p><h2>家长确认加入的轻量小组</h2>
        <div className="teacher-assignment-list">{data?.classrooms.map((membership) => <article key={membership.id}><div><strong>{membership.classroom_name}</strong><span>{membership.status === "active" ? "已加入" : "已退出"}</span></div><p>{membership.teacher.display_name}</p>{isAdmin && membership.status === "active" ? <button className="danger-text-button" disabled={working} onClick={() => void (async () => { setWorking(true); try { await leaveTeacherClassroom(activeChild.id, membership.id); setMessage("已退出班级；历史任务证据仍保留。"); await load(); } catch (reason) { setError(reason instanceof ApiClientError ? reason.message : "退出失败"); } finally { setWorking(false); } })()} type="button">退出班级</button> : null}</article>)}</div>
      </section>

      <section className="teacher-panel">
        <p className="eyebrow">老师任务</p><h2>独立于家庭今日计划</h2>
        <div className="teacher-assignment-list">{data?.assignments.map((assignment) => <article key={assignment.assignment_id}><div><strong>{assignment.teacher.display_name} · {assignment.title}</strong><span>{assignment.progress_status}</span></div><p>{assignment.instructions}</p><small>{assignment.characters.map((item) => item.character).join("、") || "无指定汉字"}</small>{assignment.progress_status !== "completed" && assignment.progress_status !== "overdue" ? <Link href={`/teacher-tasks/${assignment.assignment_id}/${activeChild.id}`}>开始 / 继续</Link> : assignment.progress_status === "overdue" ? <Link href={`/teacher-tasks/${assignment.assignment_id}/${activeChild.id}`}>逾期继续完成</Link> : <span>已完成</span>}</article>)}{data?.assignments.length === 0 ? <p className="empty-note">暂无老师任务。</p> : null}</div>
      </section>

      <section className="teacher-panel">
        <p className="eyebrow">教学观察</p><h2>老师原话</h2>
        <div className="observation-list">{data?.observations.map((item) => <article key={item.id}><div><strong>{item.teacher.display_name}</strong><time>{new Date(item.occurred_at).toLocaleString("zh-CN")}</time></div><p>{item.original_text}</p></article>)}{data?.observations.length === 0 ? <p className="empty-note">暂无教学观察。</p> : null}</div>
      </section>
    </section>
  );
}

export default function TeacherCollaborationPage() {
  return <ProtectedPage><CollaborationContent /></ProtectedPage>;
}
