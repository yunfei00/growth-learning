"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type AssignmentAnalytics,
  type TeacherAssignment,
  getTeacherAssignment,
  getTeacherAssignmentAnalytics,
} from "@/lib/api/client";

const OUTCOME_LABELS: Record<string, string> = {
  correct: "认识",
  hinted_correct: "提示后认识",
  uncertain: "不确定",
  incorrect: "不认识",
};

function AssignmentContent({ assignmentId }: { assignmentId: string }) {
  const [assignment, setAssignment] = useState<TeacherAssignment | null>(null);
  const [analytics, setAnalytics] = useState<AssignmentAnalytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      getTeacherAssignment(assignmentId),
      getTeacherAssignmentAnalytics(assignmentId),
    ])
      .then(([assignmentValue, analyticsValue]) => {
        setAssignment(assignmentValue);
        setAnalytics(analyticsValue);
      })
      .catch((reason: unknown) =>
        setError(reason instanceof ApiClientError ? reason.message : "任务结果加载失败"),
      );
  }, [assignmentId]);

  if (!assignment || !analytics) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>{error || "正在统计自己的任务结果…"}</p></section>;
  }

  return (
    <section className="teacher-page section-shell">
      <div className="teacher-hero teacher-hero-row"><div><p className="eyebrow">任务统计</p><h1>{assignment.title}</h1><p>{assignment.instructions}</p></div><Link className="button button-secondary" href="/teacher">返回工作台</Link></div>
      <div className="privacy-boundary"><strong>非排名统计</strong><span>只汇总本任务证据，不读取其他家庭学习历史，也不计算总分或儿童排名。</span></div>
      <div className="teacher-metric-grid"><article><span>总人数</span><strong>{analytics.total}</strong></article><article><span>已完成</span><strong>{analytics.completed}</strong></article><article><span>进行中</span><strong>{analytics.in_progress}</strong></article><article><span>逾期</span><strong>{analytics.overdue}</strong></article></div>

      <section className="teacher-panel">
        <p className="eyebrow">Completion</p><h2>孩子任务状态</h2>
        <div className="teacher-assignment-list">{assignment.targets.map((target) => <article key={target.child_id}><div><strong>{target.child_name}</strong><span>{target.progress_status}</span></div><p>已完成 {target.completed_item_count} / {target.total_item_count}</p>{target.child_name !== "已撤销学生" ? <Link href={`/teacher-tasks/${assignment.id}/${target.child_id}`}>打开现场任务</Link> : null}</article>)}</div>
      </section>

      <section className="teacher-panel">
        <p className="eyebrow">Recognition evidence</p><h2>逐字结果分布</h2>
        <div className="outcome-summary">{Object.entries(analytics.outcome_counts).map(([outcome, count]) => <span key={outcome}>{OUTCOME_LABELS[outcome] || outcome}：<strong>{count}</strong></span>)}</div>
        <div className="character-analytics">{Object.entries(analytics.character_outcomes).map(([character, outcomes]) => <article key={character}><strong>{character}</strong>{Object.entries(outcomes).map(([outcome, count]) => <span key={outcome}>{OUTCOME_LABELS[outcome] || outcome} {count}</span>)}</article>)}</div>
        <p className="privacy-note">常见需巩固字：{analytics.common_errors.length ? analytics.common_errors.join("、") : "数据不足"}</p>
        <p className="privacy-note">排行榜：已禁用</p>
      </section>
    </section>
  );
}

export default function TeacherAssignmentPage({ params }: { params: { assignmentId: string } }) {
  return <ProtectedPage><AssignmentContent assignmentId={params.assignmentId} /></ProtectedPage>;
}
