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
  type EnglishOverview,
  type EnglishToday,
  type MathOverview,
  type MathToday,
  type PinyinOverview,
  type PinyinToday,
  type ReadingSummary,
  type ScienceRecommendation,
  type TeacherTask,
  type AchievementSummary,
  getAchievements,
  getCharacterMasterySummary,
  getEnglishOverview,
  getEnglishToday,
  getMathOverview,
  getMathToday,
  getPinyinOverview,
  getPinyinToday,
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
  const [pinyinOverview, setPinyinOverview] = useState<PinyinOverview | null>(null);
  const [pinyinToday, setPinyinToday] = useState<PinyinToday | null>(null);
  const [mathOverview, setMathOverview] = useState<MathOverview | null>(null);
  const [mathToday, setMathToday] = useState<MathToday | null>(null);
  const [englishOverview, setEnglishOverview] = useState<EnglishOverview | null>(null);
  const [englishToday, setEnglishToday] = useState<EnglishToday | null>(null);
  const [readingSummary, setReadingSummary] = useState<ReadingSummary | null>(null);
  const [science, setScience] = useState<ScienceRecommendation[]>([]);
  const [recentGrowth, setRecentGrowth] = useState<GrowthEvent[]>([]);
  const [teacherTasks, setTeacherTasks] = useState<TeacherTask[]>([]);
  const [achievements, setAchievements] = useState<AchievementSummary | null>(null);
  const [dashboardLoaded, setDashboardLoaded] = useState(false);
  const [subjectErrors, setSubjectErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    if (status === "ready" && (!family || !activeChild)) router.replace("/onboarding");
  }, [activeChild, family, router, status]);

  useEffect(() => {
    if (!activeChild) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setDashboardLoaded(false);
      setSubjectErrors({});
      void Promise.allSettled([
      getCharacterMasterySummary(activeChild.id),
      getTodayPlan(activeChild.id),
      getPinyinOverview(activeChild.id),
      getPinyinToday(activeChild.id),
      getMathOverview(activeChild.id),
      getMathToday(activeChild.id),
      getEnglishOverview(activeChild.id),
      getEnglishToday(activeChild.id),
      getReadingSummary(activeChild.id),
      listScienceRecommendations(activeChild.id),
      getRecentGrowth(activeChild.id),
      getChildTeacherTasks(activeChild.id),
      getAchievements(activeChild.id),
      ]).then((results) => {
        if (cancelled) return;
        const errors: Record<string, string> = {};
        const use = <T,>(index: number, key: string, fallback: string): T | null => {
          const result = results[index];
          if (result.status === "fulfilled") return result.value as T;
          errors[key] = result.reason instanceof ApiClientError ? result.reason.message : fallback;
          return null;
        };
        setSummary(use<CharacterMasterySummary>(0, "characters", "识字进度暂时不可用"));
        setPlan(use<DailyPlan>(1, "characterToday", "识字今日计划暂时不可用"));
        setPinyinOverview(use<PinyinOverview>(2, "pinyin", "拼音进度暂时不可用"));
        setPinyinToday(use<PinyinToday>(3, "pinyinToday", "拼音今日计划暂时不可用"));
        setMathOverview(use<MathOverview>(4, "math", "数学进度暂时不可用"));
        setMathToday(use<MathToday>(5, "mathToday", "数学今日计划暂时不可用"));
        setEnglishOverview(use<EnglishOverview>(6, "english", "英语进度暂时不可用"));
        setEnglishToday(use<EnglishToday>(7, "englishToday", "英语今日计划暂时不可用"));
        setReadingSummary(use<ReadingSummary>(8, "reading", "阅读进度暂时不可用"));
        setScience(use<ScienceRecommendation[]>(9, "science", "科学推荐暂时不可用") ?? []);
        setRecentGrowth(use<GrowthEvent[]>(10, "growth", "成长记录暂时不可用") ?? []);
        setTeacherTasks(use<TeacherTask[]>(11, "teacher", "老师任务暂时不可用") ?? []);
        setAchievements(use<AchievementSummary>(12, "achievements", "成就暂时不可用"));
        setSubjectErrors(errors);
        setDashboardLoaded(true);
        setError("");
      });
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
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
  const nextPinyin = pinyinToday?.new_items[0] ?? pinyinToday?.review_items[0] ?? null;
  const nextMath = mathToday?.items.find((item) => !item.completed) ?? null;
  const nextEnglish = englishToday?.items.find((item) => !item.completed) ?? null;
  const characterPending = Boolean(plan && plan.status !== "completed");
  const readingPending = Boolean(plan && plan.reading.status !== "completed");
  const todayApiFailed = ["characterToday", "pinyinToday", "mathToday", "englishToday"].some(
    (key) => subjectErrors[key],
  );
  const todayStartHref = characterPending
    ? "/learn/characters"
    : pinyinToday && pinyinToday.status !== "completed" && nextPinyin
      ? `/learn/pinyin/${nextPinyin.knowledge_point_id}`
      : mathToday && mathToday.status !== "completed" && nextMath
        ? `/learn/math/${nextMath.knowledge_point_id}?source=today&count=${nextMath.problem_count}`
        : englishToday && englishToday.status !== "completed" && nextEnglish
          ? `/learn/english/${nextEnglish.knowledge_point_id}?source=today&count=${nextEnglish.exercise_count}`
          : readingPending
            ? "/read"
            : todayApiFailed
              ? "/learn"
              : null;

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
            setPinyinOverview(null);
            setPinyinToday(null);
            setMathOverview(null);
            setMathToday(null);
            setEnglishOverview(null);
            setEnglishToday(null);
            setReadingSummary(null);
            setAchievements(null);
            setScience([]);
            setSubjectErrors({});
            setDashboardLoaded(false);
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
          <span>{plan ? `${plan.plan_date} · ${plan.timezone}` : dashboardLoaded ? "各学科独立加载" : "正在生成真实计划…"}</span>
        </div>

        {dashboardLoaded ? (
          <>
            <div className="parent-today-subject-grid">
              <article className="parent-today-subject-card" data-subject="characters">
                <span>识字</span>
                {plan ? <><strong>{plan.recommended_new_count} 个新字 · {plan.review_count} 个复习</strong><small>新字完成 {plan.new_completed_count} · 复习完成 {plan.review_completed_count}</small></> : <p className="subject-error-note">{subjectErrors.characterToday}</p>}
                <Link href="/learn/characters">查看</Link>
              </article>
              <article className="parent-today-subject-card" data-subject="pinyin">
                <span>拼音</span>
                {pinyinToday ? <><strong>{pinyinToday.new_items.length} 个新内容 · {pinyinToday.review_items.length} 个复习</strong><small>完成 {pinyinToday.completed_count} / {pinyinToday.target_count}</small></> : <p className="subject-error-note">{subjectErrors.pinyinToday}</p>}
                <Link href="/learn/pinyin">查看</Link>
              </article>
              <article className="parent-today-subject-card" data-subject="math">
                <span>数学</span>
                {mathToday ? <><strong>{nextMath?.title ?? "今日数学已完成"}</strong><small>{nextMath ? `${nextMath.problem_count} 题` : `完成 ${mathToday.completed_count} / ${mathToday.target_count}`}</small></> : <p className="subject-error-note">{subjectErrors.mathToday}</p>}
                <Link href="/learn/math">查看</Link>
              </article>
              <article className="parent-today-subject-card" data-subject="english">
                <span>英语</span>
                {englishToday ? <><strong>{englishToday.items.filter((item) => !item.completed).reduce((total, item) => total + item.exercise_count, 0)} 个听音练习</strong><small>完成 {englishToday.completed_count} / {englishToday.target_count}</small></> : <p className="subject-error-note">{subjectErrors.englishToday}</p>}
                <Link href="/learn/english">查看</Link>
              </article>
              <article className="parent-today-subject-card" data-subject="reading">
                <span>阅读</span>
                {plan ? <><strong>{plan.reading.title ?? (plan.reading.status === "completed" ? "今日阅读已完成" : "1 篇故事")}</strong><small>{PERIOD_LABELS[plan.reading.status] ?? (plan.reading.status === "needs_story" ? "待生成故事" : plan.reading.status)}</small></> : <p className="subject-error-note">{subjectErrors.characterToday}</p>}
                <Link href="/read">查看</Link>
              </article>
              <article className="parent-today-subject-card" data-subject="science">
                <span>科学</span>
                {science[0] ? <><strong>{science[0].experiment.title}</strong><small>{science[0].recently_completed ? "本周已完成 · 可以查看档案" : science[0].ready_at_home ? "材料已具备" : `还缺 ${science[0].missing_required_materials.length} 种材料`}</small></> : <p className="subject-error-note">{subjectErrors.science ?? "本周暂无实验推荐"}</p>}
                <Link href="/science">查看</Link>
              </article>
            </div>
            {plan ? <div className="plan-explanation">
              <strong>今天这样安排的原因</strong>
              <p>{plan.recommendation_reason}</p>
              {plan.due_count > plan.review_count ? (
                <p>
                  还有 {plan.due_count - plan.review_count} 个到期项目会保留在队列中，按当前容量预计约
                  {" "}{plan.estimated_backlog_days} 天逐步完成。
                </p>
              ) : null}
            </div> : null}
            {plan ? <div className="period-status-row">
              <span>本周小挑战：{PERIOD_LABELS[plan.weekly_status] ?? plan.weekly_status}</span>
              <span>本月识字检测：{PERIOD_LABELS[plan.monthly_status] ?? plan.monthly_status}</span>
              <span>最近 7 天独立认识率：{retention}</span>
              <span>字库内估算识字量：{literacy}</span>
            </div> : null}
            {todayStartHref ? <Link className="button button-primary today-start" href={todayStartHref}>开始今日学习</Link> : <div className="today-complete-message"><strong>今天完成啦 ✓</strong><Link href="/learn">还想再看看</Link></div>}
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
          <span className="learning-mark">ā</span>
          <div><h3>拼音学习</h3>{pinyinOverview ? <p>已学习 {pinyinOverview.learned} / {pinyinOverview.total} · 稳定掌握 {pinyinOverview.stable}</p> : <p className="subject-error-note">{subjectErrors.pinyin ?? "正在读取真实进度…"}</p>}<Link className="card-link" href="/learn/pinyin">查看拼音档案</Link></div>
        </article>
        <article className="learning-card learning-card-active">
          <span className="learning-mark">数</span>
          <div><h3>数学启蒙</h3>{mathOverview ? <><p>已学习 {mathOverview.learned} / {mathOverview.total} 个能力 · 稳定 {mathOverview.stable}</p><p>当前：{nextMath?.title ?? mathToday?.items[0]?.title ?? "从第一个能力开始"}</p></> : <p className="subject-error-note">{subjectErrors.math ?? "正在读取真实进度…"}</p>}<Link className="card-link" href="/learn/math">查看数学档案</Link></div>
        </article>
        <article className="learning-card learning-card-active">
          <span className="learning-mark">A</span>
          <div><h3>英语启蒙</h3>{englishOverview ? <p>听懂 {englishOverview.understood_words} 个词 · 已学习 {englishOverview.letters_learned} / {englishOverview.letters_total} 个字母 · Phonics {englishOverview.phonics_practicing}</p> : <p className="subject-error-note">{subjectErrors.english ?? "正在读取真实进度…"}</p>}<Link className="card-link" href="/learn/english">查看英语档案</Link></div>
        </article>
        <article className="learning-card learning-card-active">
          <span className="learning-mark">读</span>
          <div>
            <h3>我的故事书</h3>
            <p>
              {readingSummary ? `本周 ${readingSummary.stories_read_this_week} 篇 · 独立完成 ${readingSummary.independent_this_week} 篇 · 陪读 ${readingSummary.with_help_this_week} 篇` : subjectErrors.reading ?? "正在读取真实进度…"}
            </p>
            <p>{readingSummary?.comprehension_message ?? "阅读理解数据不足"}</p>
            <Link className="card-link" href="/read">进入阅读</Link>
          </div>
        </article>
        <article className="learning-card">
          <span className="learning-mark">科</span>
          <div><h3>周末科学实验室</h3><p>{science[0] ? `${science[0].recently_completed ? "本周已完成" : "本周推荐"}：${science[0].experiment.title}` : subjectErrors.science ?? "本周暂无实验推荐"}</p><Link className="card-link" href="/science">进入实验室</Link></div>
        </article>
      </section>
    </section>
  );
}

export default function ParentHomePage() {
  return <ProtectedPage><ParentHomeContent /></ProtectedPage>;
}
