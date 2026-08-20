"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type TeacherTaskProgress,
  startTeacherTask,
  submitTeacherTask,
} from "@/lib/api/client";

const OUTCOMES = [
  { value: "correct" as const, label: "认识", hint: "独立认出" },
  { value: "hinted_correct" as const, label: "提示后认识", hint: "记录提示证据" },
  { value: "uncertain" as const, label: "不确定", hint: "暂不下结论" },
  { value: "incorrect" as const, label: "不认识", hint: "进入后续复习" },
];

function TaskContent({ assignmentId, childId }: { assignmentId: string; childId: string }) {
  const [task, setTask] = useState<TeacherTaskProgress | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      setWorking(true);
      startTeacherTask(childId, assignmentId)
        .then((value) => {
          if (active) setTask(value);
        })
        .catch((reason: unknown) => {
          if (active) {
            setError(reason instanceof ApiClientError ? reason.message : "无法开始老师任务");
          }
        })
        .finally(() => {
          if (active) setWorking(false);
        });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [assignmentId, childId]);

  const completedIds = useMemo(
    () =>
      new Set([
        ...(task?.completed_learning_point_ids ?? []),
        ...Object.keys(task?.assessment_outcomes ?? {}),
      ]),
    [task],
  );
  const current = task?.characters.find(
    (character) => !completedIds.has(character.knowledge_point_id),
  );

  const submitLearning = async () => {
    if (!task || !current) return;
    setWorking(true);
    setError("");
    try {
      const complete = task.completed_item_count + 1 === task.total_item_count;
      const value = await submitTeacherTask(childId, assignmentId, {
        learning_point_ids: [current.knowledge_point_id],
        complete,
      });
      setTask(value);
      setMessage(complete ? "任务完成，学习证据已进入统一学习档案。" : "进度已保存，可以随时离开后继续。");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "进度保存失败");
    } finally {
      setWorking(false);
    }
  };

  const submitOutcome = async (outcome: (typeof OUTCOMES)[number]["value"]) => {
    if (!task || !current) return;
    setWorking(true);
    setError("");
    try {
      const complete = task.completed_item_count + 1 === task.total_item_count;
      const value = await submitTeacherTask(childId, assignmentId, {
        assessment_items: [{ knowledge_point_id: current.knowledge_point_id, outcome }],
        complete,
      });
      setTask(value);
      setMessage(complete ? "小检测完成。逐项结果已保存并由统一掌握算法处理。" : "这一项已保存，可以继续或稍后恢复。");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "检测结果保存失败");
    } finally {
      setWorking(false);
    }
  };

  const finishSimpleTask = async () => {
    setWorking(true);
    setError("");
    try {
      const value = await submitTeacherTask(childId, assignmentId, { complete: true });
      setTask(value);
      setMessage("任务完成状态已保存。");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "还没有可关联的真实完成证据");
    } finally {
      setWorking(false);
    }
  };

  if (!task) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>{error || "正在恢复老师任务进度…"}</p></section>;
  }

  const isCharacterLearning = ["character_learning", "character_review"].includes(
    task.assignment_type,
  );
  return (
    <section className="teacher-task-page section-shell">
      <div className="teacher-task-header"><Link href="/teacher-collaboration">← 返回老师任务</Link><span>{task.teacher.display_name}</span></div>
      <div className="teacher-task-intro"><p className="eyebrow">老师任务</p><h1>{task.title}</h1><p>{task.instructions}</p><div className="task-progress"><span style={{ width: `${task.total_item_count ? (task.completed_item_count / task.total_item_count) * 100 : task.progress_status === "completed" ? 100 : 10}%` }} /></div><small>{task.completed_item_count} / {task.total_item_count || 1} · {task.progress_status}</small></div>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}

      {task.progress_status === "completed" ? <div className="teacher-task-complete"><strong>✓</strong><h2>已经完成</h2><p>刷新或再次登录后仍会保留。重复提交不会产生重复证据。</p><Link className="button button-secondary" href="/home">返回首页</Link></div> : null}

      {task.progress_status !== "completed" && current && isCharacterLearning ? <div className="character-task-card"><span>{current.pinyin}</span><strong>{current.character}</strong><p>和孩子一起读一读、说一说。</p><button className="button button-primary" disabled={working} onClick={() => void submitLearning()} type="button">{working ? "保存中…" : "完成这个字"}</button></div> : null}

      {task.progress_status !== "completed" && current && task.assignment_type === "recognition_check" ? <div className="character-task-card recognition-task"><span>请让孩子独立辨认</span><strong>{current.character}</strong><p>{current.pinyin}</p><div className="outcome-buttons">{OUTCOMES.map((outcome) => <button disabled={working} key={outcome.value} onClick={() => void submitOutcome(outcome.value)} type="button"><strong>{outcome.label}</strong><small>{outcome.hint}</small></button>)}</div></div> : null}

      {task.progress_status !== "completed" && task.assignment_type === "reading" ? <div className="teacher-task-simple"><h2>进入现有故事书完成阅读</h2><p>故事仍遵守孩子掌握快照、程序覆盖率分析和儿童内容安全。生产 AI 未配置时可阅读已有故事。</p><div className="inline-actions"><Link className="button button-primary" href="/read">打开我的故事书</Link><button className="button button-secondary" disabled={working} onClick={() => void finishSimpleTask()} type="button">我已完成真实阅读</button></div></div> : null}

      {task.progress_status !== "completed" && task.assignment_type === "freeform_instruction" ? <div className="teacher-task-simple"><h2>家长陪伴完成</h2><p>线下说明任务只记录完成状态，不会伪造认字或测评证据。</p><button className="button button-primary" disabled={working} onClick={() => void finishSimpleTask()} type="button">标记任务完成</button></div> : null}
    </section>
  );
}

export default function TeacherTaskPage({ params }: { params: { assignmentId: string; childId: string } }) {
  return <ProtectedPage><TaskContent assignmentId={params.assignmentId} childId={params.childId} /></ProtectedPage>;
}
