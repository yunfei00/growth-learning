"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { CharacterLink } from "@/components/character-link";
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
  const [selectedGroup, setSelectedGroup] = useState(1);

  const load = useCallback(async () => {
    if (!activeChild) return;
    try {
      const value = await getCourse(params.courseId, activeChild.id);
      if (value.source_type === "system") {
        const requestedGroup = Math.max(
          1,
          Number(new URLSearchParams(window.location.search).get("group") ?? "1") || 1,
        );
        const totalGroups = value.units.reduce(
          (count, unit) => count + unit.activities.length,
          0,
        );
        setSelectedGroup(Math.min(requestedGroup, Math.max(1, totalGroups)));
      }
      setCourse(value);
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
  const systemActivities = course.units.flatMap((unit) => unit.activities);
  const currentSystemActivity = systemActivities[selectedGroup - 1];
  const primarySystemPoint = currentSystemActivity?.points[0];
  const changeSystemGroup = (group: number) => {
    const nextGroup = Math.min(Math.max(1, group), systemActivities.length);
    setSelectedGroup(nextGroup);
    const url = new URL(window.location.href);
    url.searchParams.set("group", String(nextGroup));
    window.history.replaceState(window.history.state, "", url);
  };

  if (
    course.source_type === "system" &&
    course.subject === "chinese" &&
    currentSystemActivity &&
    primarySystemPoint?.knowledge_type === "chinese_character" &&
    primarySystemPoint.character
  ) {
    const returnTo = `/courses/${course.id}?group=${selectedGroup}`;
    return (
      <main className="course-detail-page system-character-path section-shell">
        <Link href="/courses">← 返回课程</Link>
        <header>
          <p className="eyebrow">1200 字连续学习路径</p>
          <h1>{course.title}</h1>
          <p>10 个字只用于目录定位；进入学习页后，上一个/下一个会沿完整字库连续前进。</p>
        </header>
        {error ? <p className="form-message form-error">{error}</p> : null}
        {message ? <p className="form-message form-success">{message}</p> : null}
        <section className="system-path-focus">
          <header>
            <div>
              <p className="eyebrow">学习目录</p>
              <h2>第 {selectedGroup} 组 · {currentSystemActivity.title}</h2>
            </div>
            <label>
              快速定位
              <select value={selectedGroup} onChange={(event) => changeSystemGroup(Number(event.target.value))}>
                {systemActivities.map((activity, index) => (
                  <option key={activity.id} value={index + 1}>第 {index + 1} 组 · {activity.title}</option>
                ))}
              </select>
            </label>
          </header>
          <div className="system-path-primary-character">
            <CharacterLink
              context={{ source: "system_path", returnTo, sequence: "system_path" }}
              knowledgePointId={primarySystemPoint.knowledge_point_id}
              speakText={primarySystemPoint.character}
            >
              <span>从本组开始</span>
              <strong>{primarySystemPoint.character}</strong>
              <small>进入后一次专注学习一个字</small>
            </CharacterLink>
          </div>
          <div className="system-path-directory" aria-label={`第${selectedGroup}组汉字目录`}>
            {currentSystemActivity.points.map((point, index) => point.character ? (
              <CharacterLink
                context={{ source: "system_path", returnTo, sequence: "system_path" }}
                key={point.knowledge_point_id}
                knowledgePointId={point.knowledge_point_id}
                speakText={point.character}
              >
                <small>{(selectedGroup - 1) * 10 + index + 1}</small>
                <strong>{point.character}</strong>
                <span className={`mastery-dot ${point.mastery_level}`}>{point.mastery_level === "unlearned" ? "待学习" : point.mastery_level === "stable" ? "稳定掌握" : "已学习"}</span>
              </CharacterLink>
            ) : null)}
          </div>
          <footer>
            <button disabled={selectedGroup <= 1} onClick={() => changeSystemGroup(selectedGroup - 1)} type="button">← 上一组</button>
            <span>{selectedGroup} / {systemActivities.length} 组</span>
            <button disabled={selectedGroup >= systemActivities.length} onClick={() => changeSystemGroup(selectedGroup + 1)} type="button">下一组 →</button>
          </footer>
          {course.enrollment_status === "active" ? (
            <button
              className="button button-secondary system-path-complete"
              disabled={currentSystemActivity.progress_status === "completed" || busy === currentSystemActivity.id}
              onClick={() => void complete(currentSystemActivity.id)}
              type="button"
            >
              {currentSystemActivity.progress_status === "completed" ? "本组已完成 ✓" : "完成本组并保存学习记录"}
            </button>
          ) : null}
        </section>
      </main>
    );
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
                {unit.projection_unavailable_count ? <span>{unit.projection_unavailable_count} 项掌握度策略未配置</span> : <><span>已学习 {unit.introduced_count}</span><span>稳定掌握 {unit.stable_count}</span><span>待学习 {unit.unlearned_count}</span></>}
              </div>
            </header>
            {unit.activities.map((activity) => (
              <article className="course-activity" key={activity.id}>
                <div>
                  <strong>{activity.title}</strong>
                  <p>{activity.instructions}</p>
                  <div className="activity-characters">
                    {activity.points.map((point) => point.knowledge_type === "chinese_character" && point.character ? (
                      <CharacterLink
                        className={point.mastery_level === "stable" ? "stable" : ""}
                        context={{
                          source: "course",
                          returnTo: `/courses/${course.id}`,
                          sequence: "course_activity",
                          contextId: activity.id,
                        }}
                        key={point.knowledge_point_id}
                        knowledgePointId={point.knowledge_point_id}
                        speakText={point.character}
                      >
                        {point.character}
                        <small>{point.pinyin}</small>
                      </CharacterLink>
                    ) : (
                      <span className="character-link" key={point.knowledge_point_id}>
                        {point.title}
                        <small>{point.projection_status === "unavailable" ? "掌握度策略未配置" : point.mastery_level}</small>
                      </span>
                    ))}
                  </div>
                </div>
                {course.enrollment_status === "active" &&
                ["character_learning", "character_review", "knowledge_learning", "guided_practice", "independent_practice", "knowledge_review"].includes(activity.activity_type) ? (
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
