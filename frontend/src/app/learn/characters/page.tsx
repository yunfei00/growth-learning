"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { CharacterLink } from "@/components/character-link";
import { ChildSwitcher } from "@/components/child-switcher";
import { CharacterSpeechReview } from "@/components/character-speech-review";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type AssessmentHistoryEntry,
  type AssessmentOutcome,
  type AssessmentSource,
  type CharacterLearningHistoryPage,
  type CharacterMasterySummary,
  type CharacterRecommendation,
  type DailyPlan,
  type LearningSettings,
  type LiteracyEstimate,
  type MasteryLevel,
  type PlannedAssessment,
  createAssessmentSession,
  createLearningSession,
  getAssessmentHistory,
  getCharacterLearningHistory,
  getCharacterMasterySummary,
  getCharacterRecommendations,
  getLearningSettings,
  getLiteracyEstimate,
  getPlannedAssessment,
  getTodayPlan,
  startPlannedAssessment,
  submitPlannedAssessment,
  updateLearningSettings,
} from "@/lib/api/client";
import { getDailyReviewEntry } from "@/lib/character-review-entry";

type View = "today" | "overview" | "new" | "quick" | "session" | "records" | "assessments" | "settings";
type HistoryPeriod = "all" | "today" | "week" | "month";

const LEVEL_LABELS: Record<MasteryLevel, string> = {
  unlearned: "未学习",
  introduced: "初识",
  recognizing: "基本认识",
  proficient: "熟练",
  stable: "稳定掌握",
};

const SOURCE_LABELS: Record<AssessmentSource, string> = {
  quick_test: "快速认字",
  daily_review: "每日复习",
  weekly_check: "本周小挑战",
  monthly_assessment: "月度识字检测",
};

const OUTCOME_LABELS: Record<AssessmentOutcome, string> = {
  correct: "认识",
  hinted_correct: "提示后认识",
  uncertain: "不确定",
  incorrect: "不认识",
};

const LEARNING_SOURCE_LABELS: Record<string, string> = {
  today_new: "今日任务",
  parent_assisted: "家长陪伴学习",
  course: "课程学习",
  teacher_assignment: "老师任务",
  story_reading: "故事识字",
  science_experiment: "科学活动",
};

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiClientError ? error.message : fallback;
}

function formatTime(value: string | null): string {
  if (!value) return "暂无";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function learningHistoryRange(period: HistoryPeriod): { learnedFrom?: string; learnedTo?: string } {
  if (period === "all") return {};
  const now = new Date();
  let start: Date;
  if (period === "today") {
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  } else if (period === "week") {
    const mondayOffset = (now.getDay() + 6) % 7;
    start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - mondayOffset);
  } else {
    start = new Date(now.getFullYear(), now.getMonth(), 1);
  }
  const end =
    period === "today"
      ? new Date(start.getFullYear(), start.getMonth(), start.getDate() + 1)
      : undefined;
  return { learnedFrom: start.toISOString(), learnedTo: end?.toISOString() };
}

function formatLearningDay(value: string): string {
  const date = new Date(value);
  const today = new Date();
  const isToday = date.toDateString() === today.toDateString();
  const formatted = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(date);
  return isToday ? `今天 · ${formatted}` : formatted;
}

function CharacterLearningContent() {
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
  const [view, setView] = useState<View>("today");
  const [summary, setSummary] = useState<CharacterMasterySummary | null>(null);
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [settings, setSettings] = useState<LearningSettings | null>(null);
  const [estimate, setEstimate] = useState<LiteracyEstimate | null>(null);
  const [recommendations, setRecommendations] = useState<CharacterRecommendation[]>([]);
  const [session, setSession] = useState<PlannedAssessment | null>(null);
  const [history, setHistory] = useState<AssessmentHistoryEntry[]>([]);
  const [learningHistory, setLearningHistory] = useState<CharacterLearningHistoryPage | null>(null);
  const [historySearch, setHistorySearch] = useState("");
  const [historyPeriod, setHistoryPeriod] = useState<HistoryPeriod>("all");
  const [quickIndex, setQuickIndex] = useState(0);
  const [quickAnswers, setQuickAnswers] = useState<
    Array<{
      knowledge_point_id: string;
      outcome: AssessmentOutcome;
      response_time_ms: number;
      hint_used?: boolean;
    }>
  >([]);
  const [answerVisible, setAnswerVisible] = useState(false);
  const [speechFallback, setSpeechFallback] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const questionStartedAt = useRef(0);
  const initialTaskHandled = useRef(false);
  const childId = activeChild?.id ?? "";

  const loadCore = useCallback(async () => {
    if (!childId) return;
    try {
      const [summaryValue, planValue, settingsValue, estimateValue] = await Promise.all([
        getCharacterMasterySummary(childId),
        getTodayPlan(childId),
        getLearningSettings(childId),
        getLiteracyEstimate(childId),
      ]);
      setSummary(summaryValue);
      setPlan(planValue);
      setSettings(settingsValue);
      setEstimate(estimateValue);
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "识字学习数据加载失败"));
    }
  }, [childId]);

  const loadLearningHistory = useCallback(async (
    page = 1,
    period: HistoryPeriod = historyPeriod,
    searchValue = historySearch,
  ) => {
    if (!childId) return;
    setIsLoading(true);
    try {
      setLearningHistory(
        await getCharacterLearningHistory(childId, {
          search: searchValue || undefined,
          ...learningHistoryRange(period),
          page,
          pageSize: 8,
        }),
      );
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "识字档案加载失败"));
    } finally {
      setIsLoading(false);
    }
  }, [childId, historyPeriod, historySearch]);

  useEffect(() => {
    if (status === "ready" && (!family || !activeChild)) router.replace("/onboarding");
  }, [activeChild, family, router, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCore(), 0);
    return () => window.clearTimeout(timer);
  }, [loadCore]);

  const resetFeedback = () => {
    setError("");
    setMessage("");
  };

  const showView = (nextView: View, extra: Record<string, string> = {}) => {
    setView(nextView);
    const url = new URL(window.location.href);
    url.search = "";
    url.searchParams.set("view", nextView);
    for (const [key, value] of Object.entries(extra)) {
      if (value) url.searchParams.set(key, value);
    }
    url.hash = "";
    window.history.replaceState(window.history.state, "", url);
  };

  const switchChild = (nextChildId: string) => {
    initialTaskHandled.current = false;
    setActiveChildId(nextChildId);
    showView("today");
    setSummary(null);
    setPlan(null);
    setSettings(null);
    setEstimate(null);
    setSession(null);
    setSpeechFallback(false);
    setRecommendations([]);
    setLearningHistory(null);
    resetFeedback();
  };

  const openSpeechSettings = () => {
    showView("settings", { focus: "speech-review" });
    window.setTimeout(() => {
      document.getElementById("speech-review-setting")?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      document.getElementById("character-review-mode")?.focus();
    }, 50);
  };

  const startNewLearning = async () => {
    if (!childId || !plan) return;
    showView("new");
    setIsLoading(true);
    resetFeedback();
    try {
      setRecommendations(
        plan.items
          .filter((item) => item.item_kind === "new")
          .map((item) => ({
            id: item.knowledge_point_id,
            character: item.character,
            pinyin: item.pinyin,
            common_words: item.common_words,
            simple_meaning: item.simple_meaning,
            example_sentence: item.example_sentence,
            mastery_level: "unlearned" as const,
            is_priority: false,
          })),
      );
    } catch (requestError) {
      setError(messageFrom(requestError, "今日新字加载失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const completeLearning = async () => {
    if (!childId || recommendations.length === 0 || !plan) return;
    const pendingIds = new Set(
      plan.items
        .filter((item) => item.item_kind === "new" && item.status === "pending")
        .map((item) => item.knowledge_point_id),
    );
    const idsToRecord = recommendations
      .map((item) => item.id)
      .filter((id) => pendingIds.has(id));
    if (idsToRecord.length === 0) {
      setMessage("今日任务已经完成；可以继续查看和练习，不会重复创建学习记录。");
      return;
    }
    setIsLoading(true);
    try {
      await createLearningSession(childId, idsToRecord, "today_new");
      setRecommendations([]);
      setMessage("今天的新字已经记入成长档案。");
      await loadCore();
    } catch (requestError) {
      setError(messageFrom(requestError, "学习记录保存失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const beginPlannedSession = async (
    source: "daily_review" | "weekly_check" | "monthly_assessment",
  ) => {
    if (!childId) return;
    setIsLoading(true);
    resetFeedback();
    try {
      const value = await startPlannedAssessment(childId, source);
      setSession(value);
      setSpeechFallback(false);
      showView("session");
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
      if (value.status === "completed") setMessage(`${SOURCE_LABELS[value.source]}已经完成。`);
    } catch (requestError) {
      setError(messageFrom(requestError, "暂时无法开始这次学习"));
    } finally {
      setIsLoading(false);
    }
  };

  const recordPlannedOutcome = async (outcome: AssessmentOutcome, speechAttemptIds: string[] = []) => {
    if (!childId || !session) return;
    const current = session.targets.find((target) => target.outcome === null);
    if (!current) return;
    setIsLoading(true);
    try {
      const isLast = session.completed_items + 1 === session.total_items;
      const updated = await submitPlannedAssessment(childId, session.id, {
        items: [
          {
            knowledge_point_id: current.knowledge_point_id,
            outcome,
            response_time_ms: Math.max(0, Math.round(performance.now() - questionStartedAt.current)),
            hint_used: outcome === "hinted_correct",
            evaluation_method: speechAttemptIds.length ? "speech_assisted" : "parent_manual",
            speech_attempt_ids: speechAttemptIds,
          },
        ],
        complete: isLast,
      });
      setSession(updated);
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
      if (updated.status === "completed") {
        setMessage(`${SOURCE_LABELS[updated.source]}完成啦 🎉`);
        await loadCore();
      }
    } catch (requestError) {
      setError(messageFrom(requestError, "结果保存失败，请稍后重试"));
    } finally {
      setIsLoading(false);
    }
  };

  const startQuickTest = async () => {
    if (!childId) return;
    showView("quick");
    setIsLoading(true);
    resetFeedback();
    try {
      setRecommendations(await getCharacterRecommendations(childId, "assessment", 5));
      setQuickIndex(0);
      setQuickAnswers([]);
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
    } catch (requestError) {
      setError(messageFrom(requestError, "快速认字题目加载失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const recordQuickOutcome = async (outcome: AssessmentOutcome) => {
    const current = recommendations[quickIndex];
    if (!current || !childId) return;
    const nextAnswers = [
      ...quickAnswers,
      {
        knowledge_point_id: current.id,
        outcome,
        response_time_ms: Math.max(0, Math.round(performance.now() - questionStartedAt.current)),
        hint_used: outcome === "hinted_correct",
      },
    ];
    setQuickAnswers(nextAnswers);
    if (quickIndex + 1 < recommendations.length) {
      setQuickIndex((value) => value + 1);
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
      return;
    }
    setIsLoading(true);
    try {
      await createAssessmentSession(childId, nextAnswers);
      setRecommendations([]);
      setMessage("快速认字完成啦 🎉 原始结果已保存。 ");
      await loadCore();
    } catch (requestError) {
      setError(messageFrom(requestError, "快速认字结果保存失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const openAssessmentHistory = async (assessmentId?: string) => {
    if (!childId) return;
    showView("assessments", assessmentId ? { assessmentId } : {});
    setSession(null);
    setIsLoading(true);
    resetFeedback();
    try {
      setHistory(await getAssessmentHistory(childId));
      if (assessmentId) setSession(await getPlannedAssessment(childId, assessmentId));
    } catch (requestError) {
      setError(messageFrom(requestError, "测试历史加载失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const openSessionDetail = async (sessionId: string) => {
    if (!childId) return;
    setIsLoading(true);
    try {
      showView("assessments", { assessmentId: sessionId });
      setSession(await getPlannedAssessment(childId, sessionId));
    } catch (requestError) {
      setError(messageFrom(requestError, "测试详情加载失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const openRecords = async (
    period: HistoryPeriod = historyPeriod,
    searchValue = historySearch,
    page = 1,
  ) => {
    setHistoryPeriod(period);
    setHistorySearch(searchValue);
    showView("records", {
      period,
      search: searchValue,
      page: String(page),
    });
    resetFeedback();
    await loadLearningHistory(page, period, searchValue);
  };

  useEffect(() => {
    if (!plan || initialTaskHandled.current) return;
    const timer = window.setTimeout(() => {
      const query = new URLSearchParams(window.location.search);
      const task = query.get("task");
      const requestedView = query.get("view") as View | null;
      if (task === "new" || requestedView === "new") {
        initialTaskHandled.current = true;
        void startNewLearning();
      } else if (task === "review" || requestedView === "session") {
        initialTaskHandled.current = true;
        if (plan.review_count > plan.review_completed_count) {
          void beginPlannedSession("daily_review");
        } else {
          showView("today");
          setMessage(
            plan.review_count > 0
              ? "今日复习已完成；查看记录不会重新创建测评。"
              : "今天没有待复习的汉字。",
          );
        }
      } else if (requestedView === "records") {
        initialTaskHandled.current = true;
        const periodValue = query.get("period");
        const period: HistoryPeriod =
          periodValue === "today" || periodValue === "week" || periodValue === "month"
            ? periodValue
            : "all";
        const searchValue = query.get("search") ?? "";
        const pageValue = Math.max(1, Number(query.get("page") ?? "1") || 1);
        void openRecords(period, searchValue, pageValue);
      } else if (requestedView === "assessments") {
        initialTaskHandled.current = true;
        void openAssessmentHistory(query.get("assessmentId") ?? undefined);
      } else if (
        requestedView === "today" ||
        requestedView === "overview" ||
        requestedView === "settings"
      ) {
        initialTaskHandled.current = true;
        showView(requestedView);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  // The URL task is intentionally handled once after today's persisted plan loads.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan]);

  const saveSettings = async () => {
    if (!childId || !settings) return;
    setIsLoading(true);
    resetFeedback();
    try {
      const nextSettings = await updateLearningSettings(childId, {
        max_new_characters_per_day: settings.max_new_characters_per_day,
        daily_review_capacity: settings.daily_review_capacity,
        weekly_assessment_enabled: settings.weekly_assessment_enabled,
        monthly_assessment_enabled: settings.monthly_assessment_enabled,
        timezone: settings.timezone,
        character_review_mode: settings.character_review_mode,
      });
      setSettings(nextSettings);
      setMessage(
        nextSettings.character_review_mode === "speech_auto"
          ? "已开启儿童朗读复习。下一次每日复习将使用麦克风。"
          : "已切换为家长陪伴复习。",
      );
    } catch (requestError) {
      setError(messageFrom(requestError, "学习设置保存失败"));
    } finally {
      setIsLoading(false);
    }
  };

  if (status === "idle" || status === "loading") {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在准备识字学习空间…</p></section>;
  }
  if (status === "error") {
    return (
      <section className="center-state section-shell">
        <h1>暂时无法进入识字学习</h1><p>{householdError}</p>
        <button className="button button-primary" onClick={() => void refresh()} type="button">重新加载</button>
      </section>
    );
  }
  if (!family || !activeChild) return null;

  const childName = activeChild.nickname || activeChild.display_name;
  const currentPlannedTarget = session?.targets.find((target) => target.outcome === null);
  const quickQuestion = recommendations[quickIndex];
  const resultCounts = session?.targets.reduce(
    (counts, item) => {
      if (item.outcome) counts[item.outcome] += 1;
      return counts;
    },
    { correct: 0, hinted_correct: 0, uncertain: 0, incorrect: 0 } as Record<AssessmentOutcome, number>,
  );
  const pendingNewIds = new Set(
    plan?.items
      .filter((item) => item.item_kind === "new" && item.status === "pending")
      .map((item) => item.knowledge_point_id) ?? [],
  );
  const newTaskCompleted = Boolean(
    plan && plan.recommended_new_count > 0 && plan.new_completed_count >= plan.recommended_new_count,
  );
  const reviewTaskCompleted = Boolean(
    plan && plan.review_count > 0 && plan.review_completed_count >= plan.review_count,
  );
  const reviewEntry = plan ? getDailyReviewEntry(plan, settings) : null;

  return (
    <section className="character-learning-page section-shell">
      <header className="learning-page-header">
        <div><p className="eyebrow">长期识字档案</p><h1>{childName}的识字学习</h1><p>原始学习和测评记录长期保留；掌握度、复习日程和每日计划均可重算。</p></div>
        <ChildSwitcher activeChildId={activeChild.id} childOptions={children} onChange={switchChild} />
      </header>

      <nav className="learning-tabs" aria-label="识字学习功能">
        <button className={view === "today" ? "active" : ""} onClick={() => showView("today")} type="button">今日任务</button>
        <button className={view === "overview" ? "active" : ""} onClick={() => showView("overview")} type="button">识字总览</button>
        <button className={view === "records" ? "active" : ""} onClick={() => void openRecords()} type="button">识字记录</button>
        <button className={view === "assessments" ? "active" : ""} onClick={() => void openAssessmentHistory()} type="button">测试历史</button>
        <button className={view === "settings" ? "active" : ""} onClick={() => showView("settings")} type="button">学习设置</button>
      </nav>

      {error ? <p className="form-message form-error learning-message" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success learning-message" role="status">{message}</p> : null}

      {view === "today" ? (
        <section className="learning-workspace phase5-today">
          <header><div><p className="eyebrow">{plan?.plan_date ?? "今天"}</p><h2>今日任务</h2></div><span>{plan?.timezone ?? "Asia/Shanghai"}</span></header>
          {plan ? (
            <>
              <div className="today-task-grid">
                <article className={newTaskCompleted ? "task-completed" : ""}><span>新字</span><strong>{plan.recommended_new_count}</strong><small>{newTaskCompleted ? "已完成 ✓" : `已完成 ${plan.new_completed_count}`}</small><button onClick={() => void startNewLearning()} disabled={plan.recommended_new_count === 0} type="button">{newTaskCompleted ? "再次打开" : "学习今日新字"}</button></article>
                <article className={`${reviewTaskCompleted ? "task-completed" : ""} ${reviewEntry?.speechEnabled ? "speech-review-entry" : ""}`}>
                  <span>{reviewEntry?.title ?? "每日复习"}</span>
                  <strong>{plan.review_count}</strong>
                  <small>{reviewTaskCompleted ? "已完成 ✓" : `待复习总数 ${plan.due_count}`}</small>
                  {!reviewEntry?.speechEnabled ? <p className="daily-review-mode">当前：家长陪伴复习</p> : <p className="daily-review-mode">{reviewTaskCompleted ? "今天已完成，查看记录不会重新测评" : "进入后开启麦克风，直接读出大字"}</p>}
                  <button onClick={() => void beginPlannedSession("daily_review")} disabled={!reviewEntry?.hasTask} type="button">{reviewEntry?.buttonLabel ?? "开始 / 继续复习"}</button>
                  {!reviewEntry?.speechEnabled && settings?.speech_review_feature_enabled && family.current_role === "admin" ? (
                    <button className="review-mode-link" onClick={openSpeechSettings} type="button">开启儿童朗读复习</button>
                  ) : null}
                </article>
                <article><span>阅读</span><strong>1 篇</strong><small>{plan.reading.title ?? (plan.reading.status === "needs_story" ? "需要生成今天的故事" : "故事已准备")}</small><Link className="task-link-button" href={plan.reading.story_version_id ? `/read/${plan.reading.story_version_id}` : "/read"}>{plan.reading.status === "completed" ? "查看已完成故事" : plan.reading.status === "in_progress" ? "继续阅读" : plan.reading.status === "pending" ? "开始阅读" : "生成今天的故事"}</Link></article>
              </div>
              <div className="plan-explanation"><strong>安排说明</strong><p>{plan.recommendation_reason}</p>{plan.due_count > plan.review_count ? <p>剩余项目不会丢失，按当前容量预计约 {plan.estimated_backlog_days} 天逐步完成。</p> : null}</div>
              <div className="period-action-grid">
                <article><p className="eyebrow">每周轻量检测</p><h3>本周小挑战</h3><p>从近期新学、较弱和少量稳定字中确定性抽样。</p><button className="button button-secondary" onClick={() => void beginPlannedSession("weekly_check")} disabled={!settings?.weekly_assessment_enabled} type="button">开始 / 查看</button></article>
                <article><p className="eyebrow">当前字库范围</p><h3>月度识字检测</h3><p>包含受控的系统未教过样本，结果不会冒充全部识字量。</p><button className="button button-secondary" onClick={() => void beginPlannedSession("monthly_assessment")} disabled={!settings?.monthly_assessment_enabled} type="button">开始 / 查看</button></article>
              </div>
            </>
          ) : <div className="center-state compact"><span className="loading-spinner" /><p>正在生成今日任务…</p></div>}
        </section>
      ) : null}

      {view === "overview" ? (
        <div className="learning-overview">
          {summary ? <div className="mastery-metric-grid">{([
            ["unlearned", "未学习", summary.unlearned], ["introduced", "初识", summary.introduced], ["recognizing", "基本认识", summary.recognizing], ["proficient", "熟练", summary.proficient], ["stable", "稳定掌握", summary.stable],
          ] as const).map(([levelValue, label, value]) => <Link href={`/learn/characters/status/${levelValue}`} key={levelValue}><span>{label}</span><strong>{value}</strong><small>字 · 点击查看</small></Link>)}</div> : <div className="center-state compact"><span className="loading-spinner" /></div>}
          <div className="literacy-panel">
            <div><p className="eyebrow">透明估算</p><h2>当前字库内估算识字量</h2></div>
            {estimate?.is_sufficient && estimate.estimate != null ? <strong>约 {Math.round(estimate.estimate)} / {estimate.catalog_size}</strong> : <strong>数据不足</strong>}
            <p>{estimate?.limitation ?? "完成至少 20 个项目的月度识字检测后再显示估算。"}</p>
            {estimate?.is_sufficient ? <small>本次抽样 {estimate.sample_size} 字 · 95% 区间约 {estimate.lower_bound}–{estimate.upper_bound} / {estimate.catalog_size}</small> : null}
          </div>
          <div className="learning-cta-grid"><button className="learning-cta" onClick={() => void startNewLearning()} type="button"><span>01</span><strong>按今日计划学习新字</strong><small>新字数量会根据复习积压和近期保留情况动态调整</small></button><button className="learning-cta" onClick={() => void startQuickTest()} type="button"><span>02</span><strong>快速认字</strong><small>用于家长临时检查，不替代每日复习和周期检测</small></button></div>
        </div>
      ) : null}

      {view === "new" ? (
        <section className="learning-workspace"><header><div><p className="eyebrow">今日新字</p><h2>{recommendations.length} 个新字</h2></div><span>{newTaskCompleted ? "已完成 ✓ · 仍可继续打开学习" : "由 Daily Plan V1 固定选择"}</span></header>{isLoading ? <div className="center-state compact"><span className="loading-spinner" /></div> : recommendations.length ? <><div className="new-character-grid">{recommendations.map((item) => <article className={!pendingNewIds.has(item.id) ? "completed" : ""} key={item.id}><CharacterLink className="new-character-link" context={{ source: "today", returnTo: "/learn/characters?view=new", sequence: "today", contextId: plan?.id, itemKind: "new" }} knowledgePointId={item.id} speakText={item.character}><strong>{item.character}</strong><p className="character-pinyin">{item.pinyin}</p><p>{item.common_words.join(" · ") || "暂无常用词"}</p><small>{item.simple_meaning || "暂无简释"}</small>{!pendingNewIds.has(item.id) ? <span>已完成 ✓</span> : null}</CharacterLink></article>)}</div>{pendingNewIds.size ? <button className="button button-primary workspace-submit" onClick={() => void completeLearning()} disabled={isLoading} type="button">完成今日新字并保存</button> : <p className="completed-task-note">今日任务已完成。你仍可点击任何汉字再次学习、朗读或练习；系统不会重复计算完成数或创建学习记录。</p>}</> : <div className="empty-learning-state"><h3>今天不安排新字</h3><p>{plan?.recommendation_reason}</p><button className="button button-secondary" onClick={() => showView("today")} type="button">返回今日任务</button></div>}</section>
      ) : null}

      {view === "session" && session ? (
        <section className="learning-workspace assessment-workspace" id={`assessment-session-${session.id}`}>
          <header><div><p className="eyebrow">{SOURCE_LABELS[session.source]}</p><h2>{session.status === "completed" ? "完成啦 🎉" : `${session.completed_items + 1} / ${session.total_items}`}</h2></div><span>{session.sampling_method} · {session.sampling_version}</span></header>
          {session.status === "completed" ? <div className="session-result"><h3>{SOURCE_LABELS[session.source]}完成</h3><div className="result-count-grid">{(Object.keys(OUTCOME_LABELS) as AssessmentOutcome[]).map((outcome) => <article key={outcome}><span>{OUTCOME_LABELS[outcome]}</span><strong>{resultCounts?.[outcome] ?? 0}</strong></article>)}</div><div className="completed-review-characters">{session.targets.map((target) => <CharacterLink context={{ source: "review", returnTo: `/learn/characters?view=assessments&assessmentId=${session.id}#assessment-session-${session.id}`, sequence: "assessment_session", contextId: session.id }} knowledgePointId={target.knowledge_point_id} key={target.knowledge_point_id} speakText={target.character}><strong>{target.character}</strong><span>{target.pinyin}</span><small>查看这个字</small></CharacterLink>)}</div><p>没有分数或排名；再次打开汉字不会重复提交结果或修改掌握度。</p><button className="button button-primary" onClick={() => showView("today")} type="button">回到今日任务</button></div> : currentPlannedTarget ? (settings?.character_review_mode === "speech_auto" && settings.speech_review_feature_enabled && !speechFallback ? <CharacterSpeechReview childId={childId} disabled={isLoading} onFallback={() => setSpeechFallback(true)} onOutcome={(outcome, attemptIds) => recordPlannedOutcome(outcome, attemptIds)} onSessionUpdate={setSession} session={session} target={currentPlannedTarget} /> : <div className="recognition-card"><strong className="recognition-glyph">{currentPlannedTarget.character}</strong>{answerVisible ? <div className="recognition-answer"><p>{currentPlannedTarget.pinyin}</p><small>看到提示后，请选择“提示后认识”</small></div> : <p className="answer-hidden">拼音和答案默认隐藏</p>}<div className="outcome-grid"><button onClick={() => void recordPlannedOutcome("correct")} disabled={isLoading} type="button">认识</button><button onClick={() => { setAnswerVisible(true); }} className="hint-button" disabled={isLoading} type="button">查看提示</button><button onClick={() => void recordPlannedOutcome("hinted_correct")} disabled={!answerVisible || isLoading} type="button">提示后认识</button><button onClick={() => void recordPlannedOutcome("uncertain")} disabled={isLoading} type="button">不确定</button><button onClick={() => void recordPlannedOutcome("incorrect")} disabled={isLoading} type="button">不认识</button></div></div>) : null}
        </section>
      ) : null}

      {view === "quick" ? (
        <section className="learning-workspace assessment-workspace"><header><div><p className="eyebrow">临时检查</p><h2>快速认字</h2></div><span>不会替代每日复习队列</span></header>{quickQuestion ? <div className="recognition-card"><strong className="recognition-glyph">{quickQuestion.character}</strong>{answerVisible ? <div className="recognition-answer"><p>{quickQuestion.pinyin}</p><small>{quickQuestion.simple_meaning}</small></div> : <p className="answer-hidden">答案默认隐藏</p>}<div className="outcome-grid"><button onClick={() => void recordQuickOutcome("correct")} type="button">认识</button><button className="hint-button" onClick={() => setAnswerVisible(true)} type="button">查看提示</button><button disabled={!answerVisible} onClick={() => void recordQuickOutcome("hinted_correct")} type="button">提示后认识</button><button onClick={() => void recordQuickOutcome("uncertain")} type="button">不确定</button><button onClick={() => void recordQuickOutcome("incorrect")} type="button">不认识</button></div></div> : <div className="empty-learning-state"><h3>暂无可检查的已学汉字</h3><button className="button button-secondary" onClick={() => showView("overview")} type="button">返回总览</button></div>}</section>
      ) : null}

      {view === "records" ? (
        <section className="learning-workspace learning-history-workspace">
          <header>
            <div><p className="eyebrow">真实学习证据</p><h2>识字记录</h2></div>
            <span>只显示真正产生过 LearningRecord 的学习</span>
          </header>
          {learningHistory ? (
            <div className="learning-history-summary">
              <span>已学习 <strong>{learningHistory.distinct_characters}</strong> 个字</span>
              <span>本周新增 <strong>{learningHistory.this_week_first_learned}</strong> 个</span>
              <span>共 <strong>{learningHistory.total_records}</strong> 条学习证据</span>
            </div>
          ) : null}
          <form
            className="learning-history-filters"
            onSubmit={(event) => {
              event.preventDefault();
              void openRecords(historyPeriod, historySearch, 1);
            }}
          >
            <div className="history-period-tabs" role="group" aria-label="学习记录时间范围">
              {(["all", "today", "week", "month"] as HistoryPeriod[]).map((period) => (
                <button
                  className={historyPeriod === period ? "active" : ""}
                  key={period}
                  onClick={() => void openRecords(period, historySearch, 1)}
                  type="button"
                >
                  {{ all: "全部", today: "今天", week: "本周", month: "本月" }[period]}
                </button>
              ))}
            </div>
            <label>
              <span className="sr-only">搜索汉字</span>
              <input
                placeholder="搜索汉字"
                value={historySearch}
                onChange={(event) => setHistorySearch(event.target.value)}
              />
            </label>
            <button className="button button-secondary" type="submit">搜索</button>
          </form>
          {isLoading && !learningHistory ? (
            <div className="center-state compact"><span className="loading-spinner" /></div>
          ) : learningHistory?.items.length ? (
            <div className="learning-history-timeline">
              {learningHistory.items.map((learningSession) => {
                const returnQuery = new URLSearchParams({
                  view: "records",
                  period: historyPeriod,
                  page: String(learningHistory.page),
                });
                if (historySearch) returnQuery.set("search", historySearch);
                const returnTo = `/learn/characters?${returnQuery.toString()}#learning-session-${learningSession.session_id}`;
                return (
                  <article id={`learning-session-${learningSession.session_id}`} key={learningSession.session_id}>
                    <header>
                      <div>
                        <h3>{formatLearningDay(learningSession.completed_at ?? learningSession.started_at)}</h3>
                        <p>{LEARNING_SOURCE_LABELS[learningSession.source] ?? "识字学习"} · 学习 {learningSession.records.length} 个字</p>
                      </div>
                      <time>{new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(learningSession.completed_at ?? learningSession.started_at))}</time>
                    </header>
                    <div className="learning-history-characters">
                      {learningSession.records.map((record) => (
                        <CharacterLink
                          context={{ source: "records", returnTo, sequence: "learning_session", contextId: learningSession.session_id }}
                          key={record.record_id}
                          knowledgePointId={record.knowledge_point_id}
                          speakText={record.character}
                        >
                          <strong>{record.character}</strong>
                          <span className={`mastery-pill ${record.mastery_level}`}>{LEVEL_LABELS[record.mastery_level]}</span>
                        </CharacterLink>
                      ))}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="empty-learning-state"><h3>还没有符合条件的学习记录</h3><p>完成一次正式汉字学习后，会按日期和学习批次出现在这里；仅测评过的字不会混入。</p></div>
          )}
          {learningHistory && learningHistory.pages > 1 ? (
            <nav aria-label="识字记录分页" className="history-pagination">
              <button disabled={learningHistory.page <= 1} onClick={() => void openRecords(historyPeriod, historySearch, learningHistory.page - 1)} type="button">上一页</button>
              <span>{learningHistory.page} / {learningHistory.pages}</span>
              <button disabled={learningHistory.page >= learningHistory.pages} onClick={() => void openRecords(historyPeriod, historySearch, learningHistory.page + 1)} type="button">下一页</button>
            </nav>
          ) : null}
        </section>
      ) : null}

      {view === "assessments" ? (
        <section className="learning-workspace"><header><div><p className="eyebrow">真实测评证据</p><h2>测试历史</h2></div><span>每日复习 · 周度小挑战 · 月度识字检测</span></header>{isLoading ? <div className="center-state compact"><span className="loading-spinner" /></div> : history.length ? <div className="assessment-history-list">{history.map((item) => <button key={item.id} onClick={() => void openSessionDetail(item.id)} type="button"><div><strong>{SOURCE_LABELS[item.source]}</strong><span>{formatTime(item.started_at)}</span></div><div><span>{item.item_count} 项</span><span>认识 {item.correct}</span><span>提示 {item.hinted_correct}</span><span>不确定 {item.uncertain}</span><span>不认识 {item.incorrect}</span></div></button>)}</div> : <div className="empty-learning-state"><h3>还没有测试记录</h3><p>完成每日复习、周度或月度检测后会显示在这里。</p></div>}{session ? <div className="history-session-detail" id={`assessment-session-${session.id}`}><h3>{SOURCE_LABELS[session.source]} · {formatTime(session.started_at)}</h3><div className="target-chip-list">{session.targets.map((target) => target.outcome ? <CharacterLink context={{ source: "review", returnTo: `/learn/characters?view=assessments&assessmentId=${session.id}#assessment-session-${session.id}`, sequence: "assessment_session", contextId: session.id }} key={target.knowledge_point_id} knowledgePointId={target.knowledge_point_id} speakText={target.character}><strong>{target.character}</strong><span>{OUTCOME_LABELS[target.outcome]}</span><small>查看这个字</small></CharacterLink> : <span key={target.knowledge_point_id}><strong>{target.character}</strong>未完成<small>{target.sampling_class}</small></span>)}</div></div> : null}</section>
      ) : null}

      {view === "settings" ? (
        <section className="learning-workspace"><header><div><p className="eyebrow">家长管理</p><h2>学习设置</h2></div><span>只有家庭管理员可以修改</span></header>{settings ? <div className="learning-settings-form"><label>每日最多新字<input type="number" min="0" max="20" value={settings.max_new_characters_per_day} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, max_new_characters_per_day: Number(event.target.value) })} /></label><label>每日复习容量<input type="number" min="1" max="100" value={settings.daily_review_capacity} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, daily_review_capacity: Number(event.target.value) })} /></label><label className="toggle-setting"><input type="checkbox" checked={settings.weekly_assessment_enabled} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, weekly_assessment_enabled: event.target.checked })} />开启周度小挑战</label><label className="toggle-setting"><input type="checkbox" checked={settings.monthly_assessment_enabled} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, monthly_assessment_enabled: event.target.checked })} />开启月度识字检测</label><label>时区<input value={settings.timezone} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })} /></label><label id="speech-review-setting">每日复习方式<select id="character-review-mode" value={settings.character_review_mode} disabled={family.current_role !== "admin" || !settings.speech_review_feature_enabled} onChange={(event) => setSettings({ ...settings, character_review_mode: event.target.value as LearningSettings["character_review_mode"] })}><option value="parent_manual">普通复习（家长判断）</option><option value="speech_auto">儿童朗读复习（自动听读）</option></select><small>语音自动复习是实验功能，需要浏览器麦克风权限和 HTTPS 安全地址。</small></label>{!settings.speech_review_feature_enabled ? <p className="role-note">自动听读功能正在逐步开放，当前可继续使用普通复习模式。</p> : null}{family.current_role === "admin" ? <button className="button button-primary" onClick={() => void saveSettings()} disabled={isLoading} type="button">保存设置</button> : <p className="role-note">陪伴者可以学习和测评，但不能修改家庭学习设置。</p>}</div> : <div className="center-state compact"><span className="loading-spinner" /></div>}</section>
      ) : null}
    </section>
  );
}

export default function CharacterLearningPage() {
  return <ProtectedPage><CharacterLearningContent /></ProtectedPage>;
}
