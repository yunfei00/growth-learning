"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type Course,
  completeCourseActivity,
  getCourse,
} from "@/lib/api/client";

function CourseDetailContent() {
  const params = useParams<{ courseId: string }>();
  const { activeChild } = useActiveChild();
  const [course, setCourse] = useState<Course | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      setCourse(await getCourse(params.courseId, activeChild.id));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "课程加载失败");
    }
  }, [activeChild, params.courseId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const complete = async (activityId: string) => {
    if (!activeChild) return;
    setBusy(activityId);
    try {
      const result = await completeCourseActivity(activeChild.id, activityId);
      setMessage(`已保存 ${result.learning_records_created} 条 canonical 学习记录。`);
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "无法完成活动");
    } finally {
      setBusy("");
    }
  };

  if (!course) {
    return <main className="center-state section-shell">{error || "正在加载课程…"}</main>;
  }
  return (
    <main className="course-detail-page section-shell">
      <Link href="/courses">← 返回课程</Link>
      <header>
        <p className="eyebrow">课程详情</p>
        <h1>{course.title}</h1>
        <p>{course.description}</p>
      </header>
      <aside className="course-principle">
        <strong>课程完成 {course.progress_percent}%</strong>
        <span>这是活动完成比例，不是知识掌握比例。</span>
      </aside>
      {error ? <p className="form-message form-error">{error}</p> : null}
      {message ? <p className="form-message form-success">{message}</p> : null}
      <div className="course-unit-list">
        {course.units.map((unit) => (
          <section className="course-unit" key={unit.id}>
            <header>
              <div>
                <p>Unit {unit.order_index + 1}</p>
                <h2>{unit.title}</h2>
              </div>
              <div className="course-stat-row">
                <span>已学习 {unit.introduced_count}</span>
                <span>稳定掌握 {unit.stable_count}</span>
                <span>待学习 {unit.unlearned_count}</span>
              </div>
            </header>
            {unit.activities.map((activity) => (
              <article className="course-activity" key={activity.id}>
                <div>
                  <strong>{activity.title}</strong>
                  <p>{activity.instructions}</p>
                  <div className="activity-characters">
                    {activity.points.map((point) => (
                      <span
                        className={point.mastery_level === "stable" ? "stable" : ""}
                        key={point.knowledge_point_id}
                        title={`${point.pinyin} · ${point.mastery_level}`}
                      >
                        {point.character}
                      </span>
                    ))}
                  </div>
                </div>
                {course.enrollment_status === "active" &&
                ["character_learning", "character_review"].includes(activity.activity_type) ? (
                  <button
                    disabled={activity.progress_status === "completed" || busy === activity.id}
                    onClick={() => void complete(activity.id)}
                  >
                    {activity.progress_status === "completed" ? "已完成" : "完成本活动"}
                  </button>
                ) : null}
              </article>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}

export default function CourseDetailPage() {
  return (
    <ProtectedPage>
      <CourseDetailContent />
    </ProtectedPage>
  );
}
