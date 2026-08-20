"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type CharacterMasterySummary,
  type DailyPlan,
  type GrowthEvent,
  type ReadingSummary,
  type ScienceRecommendation,
  type TeacherTask,
  type AchievementSummary,
  getAchievements,
  getCharacterMasterySummary,
  getRecentGrowth,
  getReadingSummary,
  getTodayPlan,
  getChildTeacherTasks,
  listScienceRecommendations,
} from "@/lib/api/client";

function formatAge(birthDate: string): string {
  const birth = new Date(`${birthDate}T00:00:00`);
  const today = new Date();
  let months =
    (today.getFullYear() - birth.getFullYear()) * 12 + today.getMonth() - birth.getMonth();
  if (today.getDate() < birth.getDate()) months -= 1;
  months = Math.max(0, months);
  const years = Math.floor(months / 12);
  const remainingMonths = months % 12;
  if (years === 0) return `${remainingMonths}个月`;
  return remainingMonths === 0 ? `${years}岁` : `${years}岁${remainingMonths}个月`;
}

const PERIOD_LABELS: Record<string, string> = {
  pending: "待完成",
  in_progress: "进行中",
  completed: "已完成",
  disabled: "未开启",
};

function ParentHomeContent() {
  const router = useRouter();
  const {
    status,
    family,
    children,
    activeChild,
    error: householdError,
    setActiveChildId,
    refresh,
  } = useActiveChild();
  const [summary, setSummary] = useState<CharacterMasterySummary | null>(null);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [readingSummary, setReadingSummary] = useState<ReadingSummary | null>(null);
  const [science, setScience] = useState<ScienceRecommendation[]>([]);
  const [recentGrowth, setRecentGrowth] = useState<GrowthEvent[]>([]);
  const [teacherTasks, setTeacherTasks] = useState<TeacherTask[]>([]);
  const [achievements, setAchievements] = useState<AchievementSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (status === "ready" && (!family || !activeChild)) router.replace("/onboarding");
  }, [activeChild, family, router, status]);

  useEffect(() => {
    if (!activeChild) return;
    let cancelled = false;
    Promise.all([
      getCharacterMasterySummary(activeChild.id),
      getTodayPlan(activeChild.id),
      getReadingSummary(activeChild.id),
      listScienceRecommendations(activeChild.id),
      getRecentGrowth(activeChild.id),
      getChildTeacherTasks(activeChild.id),
      getAchievements(activeChild.id),
    ])
      .then(([summaryValue, planValue, readingValue, scienceValue, growthValue, taskValue, achievementValue]) => {
        if (!cancelled) {
          setSummary(summaryValue);
          setPlan(planValue);
          setReadingSummary(readingValue);
          setScience(scienceValue);
          setRecentGrowth(growthValue);
          setTeacherTasks(taskValue);
          setAchievements(achievementValue);
          setError("");
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setError(
            requestError instanceof ApiClientError
              ? requestError.message
              : "暂时无法加载今天的学习计划",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeChild]);

  if (status === "idle" || status === "loading") {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在加载家庭和孩子信息…</p>
      </section>
    );
  }
  if (status === "error") {
    return (
      <section className="center-state section-shell">
        <h1>暂时无法进入家长首页</h1>
        <p>{householdError}</p>
        <button className="button button-primary" onClick={() => void refresh()} type="button">
          重新加载
        </button>
      </section>
    );
  }
  if (!family || !activeChild) return null;

  const childName = activeChild.nickname || activeChild.display_name;
  const learned = summary
    ? summary.introduced + summary.recognizing + summary.proficient + summary.stable
    : null;
  const retention =
    plan?.recent_independent_correct_rate == null
      ? "数据不足"
      : `${Math.round(plan.recent_independent_correct_rate * 100)}%`;
  const literacy =
    plan?.literacy_status === "available" && plan.literacy_estimate != null
      ? `约 ${Math.round(plan.literacy_estimate)} / ${plan.literacy_catalog_size}`
      : "数据不足";

  return (
    <section className="dashboard-page section-shell">
      <div className="dashboard-toolbar">
        <div>
          <p className="eyebrow">家长首页</p>
          <h1>家庭：{family.name}</h1>
          <p className="role-note">
            当前权限：{family.current_role === "admin" ? "家庭管理员" : "陪伴者"}
          </p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={(childId) => {
            setSummary(null);
            setPlan(null);
            setReadingSummary(null);
            setAchievements(null);
            setError("");
            setActiveChildId(childId);
          }}
        />
      </div>

      <div className="welcome-card">
        <div>
          <p className="eyebrow">成长档案</p>
          <h2>你好，{childName} 👋</h2>
          <p>{formatAge(activeChild.birth_date)}</p>
        </div>
        <div className="profile-mark" aria-hidden="true">
          {childName.slice(0, 1)}
        </div>
        <Link className="enter-child-mode" href="/kids">
          <span aria-hidden="true">🌱</span>
          进入孩子模式
        </Link>
      </div>

      {error ? <p className="form-message form-error">{error}</p> : null}

      <section className="today-section">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Today</p>
            <h2>今日任务</h2>
          </div>
          <span>{plan ? `${plan.plan_date} · ${plan.timezone}` : "正在生成真实计划…"}</span>
        </div>

        {plan ? (
          <>
            <div className="today-plan-grid">
              <article>
                <span>今日新字</span>
                <strong>{plan.recommended_new_count}</strong>
                <small>已完成 {plan.new_completed_count}</small>
              </article>
              <article>
                <span>今日复习</span>
                <strong>{plan.review_count}</strong>
                <small>待复习总数 {plan.due_count}</small>
              </article>
              <article>
                <span>最近 7 天独立认识率</span>
                <strong className="metric-text">{retention}</strong>
                <small>仅作保留情况参考</small>
              </article>
              <article>
                <span>当前字库内估算识字量</span>
                <strong className="metric-text">{literacy}</strong>
                <small>不是全部汉字识字量</small>
              </article>
            </div>
            <div className="plan-explanation">
              <strong>今天这样安排的原因</strong>
              <p>{plan.recommendation_reason}</p>
              {plan.due_count > plan.review_count ? (
                <p>
                  还有 {plan.due_count - plan.review_count} 个到期项目会保留在队列中，按当前容量预计约
                  {" "}{plan.estimated_backlog_days} 天逐步完成。
                </p>
              ) : null}
            </div>
            <div className="period-status-row">
              <span>本周小挑战：{PERIOD_LABELS[plan.weekly_status] ?? plan.weekly_status}</span>
              <span>本月识字检测：{PERIOD_LABELS[plan.monthly_status] ?? plan.monthly_status}</span>
              <span>
                今日阅读：{plan.reading.status === "completed" ? "已完成" : plan.reading.status === "in_progress" ? "进行中" : plan.reading.status === "pending" ? "待阅读" : "需要生成故事"}
              </span>
            </div>
            <Link className="button button-primary today-start" href="/learn/characters">
              开始今日学习
            </Link>
          </>
        ) : (
          <div className="center-state compact">
            <span className="loading-spinner" aria-hidden="true" />
            <p>正在根据复习积压和近期表现生成今日任务…</p>
          </div>
        )}
      </section>

      <section className="teacher-tasks-home">
        <div className="section-title-row">
          <div><p className="eyebrow">老师任务</p><h2>家长授权的教学协作</h2></div>
          <Link href="/teacher-collaboration">老师协作设置</Link>
        </div>
        <div className="teacher-task-home-list">
          {teacherTasks.slice(0, 4).map((task) => (
            <article key={task.assignment_id}>
              <div><strong>{task.teacher.display_name} · {task.title}</strong><span>{task.progress_status}</span></div>
              <p>{task.instructions}</p>
              <small>{task.characters.map((item) => item.character).join("、") || "阅读 / 线下说明"}</small>
              {task.progress_status !== "completed" ? <Link href={`/teacher-tasks/${task.assignment_id}/${activeChild.id}`}>开始 / 继续</Link> : <span>已完成</span>}
            </article>
          ))}
          {teacherTasks.length === 0 ? <p className="empty-note">当前没有老师任务，不影响今日新字、复习、阅读或科学实验。</p> : null}
        </div>
      </section>

      <section className="recent-growth-home">
        <div className="section-title-row">
          <div><p className="eyebrow">最近成长</p><h2>值得记住的瞬间</h2></div>
          <Link href="/growth">查看全部</Link>
        </div>
        <div className="recent-growth-list">
          {recentGrowth.slice(0, 5).map((event) => (
            <article key={event.id}>
              <span>✓</span><div><strong>{event.title}</strong><small>{new Date(event.occurred_at).toLocaleDateString("zh-CN")}</small></div>
            </article>
          ))}
          {recentGrowth.length === 0 ? <p>从学习、阅读、科学探索或一条家庭记录开始积累成长瞬间。</p> : null}
        </div>
      </section>

      <section className="parent-achievement-card">
        <div>
          <p className="eyebrow">Positive encouragement</p>
          <h2>最近成就</h2>
          {achievements?.achievements[0] ? (
            <p>{achievements.achievements[0].icon} {achievements.achievements[0].title} · {achievements.achievements[0].description}</p>
          ) : (
            <p>真实完成一次学习、阅读或实验后，成长时刻会出现在这里。</p>
          )}
        </div>
        <div className="parent-achievement-actions">
          {achievements?.stars_enabled ? <strong>⭐ {achievements.star_balance}</strong> : null}
          <Link href="/kids/achievements">查看孩子成就</Link>
          <Link href="/settings">鼓励设置</Link>
        </div>
      </section>

      <section className="learning-grid">
        <article className="learning-card learning-card-active">
          <span className="learning-mark">字</span>
          <div>
            <h3>识字学习</h3>
            <p>已接触 {learned ?? "…"} 字 · 稳定掌握 {summary?.stable ?? "…"} 字</p>
            <Link className="card-link" href="/learn/characters">
              查看识字档案
            </Link>
          </div>
        </article>
        <article className="learning-card learning-card-active">
          <span className="learning-mark">读</span>
          <div>
            <h3>我的故事书</h3>
            <p>
              本周 {readingSummary?.stories_read_this_week ?? 0} 篇 · 独立完成 {readingSummary?.independent_this_week ?? 0} 篇 · 陪读 {readingSummary?.with_help_this_week ?? 0} 篇
            </p>
            <p>{readingSummary?.comprehension_message ?? "阅读理解数据不足"}</p>
            <Link className="card-link" href="/read">进入阅读</Link>
          </div>
        </article>
        <article className="learning-card">
          <span className="learning-mark">科</span>
          <div><h3>周末科学实验室</h3><p>{science[0] ? `本周推荐：${science[0].experiment.title}` : "正在准备真实实验推荐"}</p><Link className="card-link" href="/science">进入实验室</Link></div>
        </article>
      </section>
    </section>
  );
}

export default function ParentHomePage() {
  return <ProtectedPage><ParentHomeContent /></ProtectedPage>;
}
