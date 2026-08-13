"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type AssessmentHistoryEntry,
  type AssessmentOutcome,
  type AssessmentSource,
  type CharacterMasteryDetail,
  type CharacterMasteryPage,
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
  getCharacterMasteryDetail,
  getCharacterMasterySummary,
  getCharacterRecommendations,
  getLearningSettings,
  getLiteracyEstimate,
  getPlannedAssessment,
  getTodayPlan,
  listCharacterMastery,
  startPlannedAssessment,
  submitPlannedAssessment,
  updateCharacterPriority,
  updateLearningSettings,
} from "@/lib/api/client";

type View = "today" | "overview" | "new" | "quick" | "session" | "records" | "assessments" | "settings";

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

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiClientError ? error.message : fallback;
}

function formatTime(value: string | null): string {
  if (!value) return "暂无";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
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
  const [masteryHistory, setMasteryHistory] = useState<CharacterMasteryPage | null>(null);
  const [detail, setDetail] = useState<CharacterMasteryDetail | null>(null);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<MasteryLevel | "">("");
  const [priorityOnly, setPriorityOnly] = useState(false);
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
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const questionStartedAt = useRef(0);
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

  const loadMasteryHistory = useCallback(async (page = 1) => {
    if (!childId) return;
    setIsLoading(true);
    try {
      setMasteryHistory(
        await listCharacterMastery(childId, {
          search,
          masteryLevel: level || undefined,
          priority: priorityOnly ? true : undefined,
          page,
          pageSize: 12,
        }),
      );
      setError("");
    } catch (requestError) {
      setError(messageFrom(requestError, "识字档案加载失败"));
    } finally {
      setIsLoading(false);
    }
  }, [childId, level, priorityOnly, search]);

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

  const switchChild = (nextChildId: string) => {
    setActiveChildId(nextChildId);
    setView("today");
    setSummary(null);
    setPlan(null);
    setSettings(null);
    setEstimate(null);
    setSession(null);
    setRecommendations([]);
    setMasteryHistory(null);
    setDetail(null);
    resetFeedback();
  };

  const startNewLearning = async () => {
    if (!childId || !plan) return;
    setView("new");
    setIsLoading(true);
    resetFeedback();
    try {
      setRecommendations(
        plan.items
          .filter((item) => item.item_kind === "new" && item.status === "pending")
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
    if (!childId || recommendations.length === 0) return;
    setIsLoading(true);
    try {
      await createLearningSession(childId, recommendations.map((item) => item.id));
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
      setView("session");
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
      if (value.status === "completed") setMessage(`${SOURCE_LABELS[value.source]}已经完成。`);
    } catch (requestError) {
      setError(messageFrom(requestError, "暂时无法开始这次学习"));
    } finally {
      setIsLoading(false);
    }
  };

  const recordPlannedOutcome = async (outcome: AssessmentOutcome) => {
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
    setView("quick");
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

  const openAssessmentHistory = async () => {
    if (!childId) return;
    setView("assessments");
    setSession(null);
    setIsLoading(true);
    resetFeedback();
    try {
      setHistory(await getAssessmentHistory(childId));
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
      setSession(await getPlannedAssessment(childId, sessionId));
    } catch (requestError) {
      setError(messageFrom(requestError, "测试详情加载失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const openRecords = async () => {
    setView("records");
    setDetail(null);
    resetFeedback();
    await loadMasteryHistory();
  };

  const togglePriority = async (knowledgePointId: string, value: boolean) => {
    if (!childId) return;
    setIsLoading(true);
    try {
      await updateCharacterPriority(childId, knowledgePointId, value);
      await Promise.all([loadMasteryHistory(masteryHistory?.page ?? 1), loadCore()]);
      if (detail?.state.knowledge_point_id === knowledgePointId) {
        setDetail(await getCharacterMasteryDetail(childId, knowledgePointId));
      }
    } catch (requestError) {
      setError(messageFrom(requestError, "重点复习设置失败"));
    } finally {
      setIsLoading(false);
    }
  };

  const saveSettings = async () => {
    if (!childId || !settings) return;
    setIsLoading(true);
    resetFeedback();
    try {
      setSettings(await updateLearningSettings(childId, settings));
      setMessage("学习设置已保存；已有今日计划保持不变，明天按新设置生成。 ");
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

  return (
    <section className="character-learning-page section-shell">
      <header className="learning-page-header">
        <div><p className="eyebrow">长期识字档案</p><h1>{childName}的识字学习</h1><p>原始学习和测评记录长期保留；掌握度、复习日程和每日计划均可重算。</p></div>
        <ChildSwitcher activeChildId={activeChild.id} childOptions={children} onChange={switchChild} />
      </header>

      <nav className="learning-tabs" aria-label="识字学习功能">
        <button className={view === "today" ? "active" : ""} onClick={() => setView("today")} type="button">今日任务</button>
        <button className={view === "overview" ? "active" : ""} onClick={() => setView("overview")} type="button">识字总览</button>
        <button className={view === "records" ? "active" : ""} onClick={() => void openRecords()} type="button">识字记录</button>
        <button className={view === "assessments" ? "active" : ""} onClick={() => void openAssessmentHistory()} type="button">测试历史</button>
        <button className={view === "settings" ? "active" : ""} onClick={() => setView("settings")} type="button">学习设置</button>
      </nav>

      {error ? <p className="form-message form-error learning-message" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success learning-message" role="status">{message}</p> : null}

      {view === "today" ? (
        <section className="learning-workspace phase5-today">
          <header><div><p className="eyebrow">{plan?.plan_date ?? "今天"}</p><h2>今日任务</h2></div><span>{plan?.timezone ?? "Asia/Shanghai"}</span></header>
          {plan ? (
            <>
              <div className="today-task-grid">
                <article><span>新字</span><strong>{plan.recommended_new_count}</strong><small>已完成 {plan.new_completed_count}</small><button onClick={() => void startNewLearning()} disabled={plan.recommended_new_count === 0 || plan.new_completed_count >= plan.recommended_new_count} type="button">学习今日新字</button></article>
                <article><span>复习</span><strong>{plan.review_count}</strong><small>待复习总数 {plan.due_count}</small><button onClick={() => void beginPlannedSession("daily_review")} disabled={plan.review_count === 0} type="button">开始 / 继续复习</button></article>
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
            ["未学习", summary.unlearned], ["初识", summary.introduced], ["基本认识", summary.recognizing], ["熟练", summary.proficient], ["稳定掌握", summary.stable],
          ] as const).map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong><small>字</small></article>)}</div> : <div className="center-state compact"><span className="loading-spinner" /></div>}
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
        <section className="learning-workspace"><header><div><p className="eyebrow">今日新字</p><h2>{recommendations.length} 个新字</h2></div><span>由 Daily Plan V1 固定选择</span></header>{isLoading ? <div className="center-state compact"><span className="loading-spinner" /></div> : recommendations.length ? <><div className="new-character-grid">{recommendations.map((item) => <article key={item.id}><strong>{item.character}</strong><p className="character-pinyin">{item.pinyin}</p><p>{item.common_words.join(" · ") || "暂无常用词"}</p><small>{item.simple_meaning || "暂无简释"}</small></article>)}</div><button className="button button-primary workspace-submit" onClick={() => void completeLearning()} disabled={isLoading} type="button">完成今日新字并保存</button></> : <div className="empty-learning-state"><h3>今天不安排新字</h3><p>{plan?.recommendation_reason}</p><button className="button button-secondary" onClick={() => setView("today")} type="button">返回今日任务</button></div>}</section>
      ) : null}

      {view === "session" && session ? (
        <section className="learning-workspace assessment-workspace"><header><div><p className="eyebrow">{SOURCE_LABELS[session.source]}</p><h2>{session.status === "completed" ? "完成啦 🎉" : `${session.completed_items + 1} / ${session.total_items}`}</h2></div><span>{session.sampling_method} · {session.sampling_version}</span></header>{session.status === "completed" ? <div className="session-result"><h3>{SOURCE_LABELS[session.source]}完成</h3><div className="result-count-grid">{(Object.keys(OUTCOME_LABELS) as AssessmentOutcome[]).map((outcome) => <article key={outcome}><span>{OUTCOME_LABELS[outcome]}</span><strong>{resultCounts?.[outcome] ?? 0}</strong></article>)}</div><p>没有分数或排名；需要关注的字已经进入后续复习日程。</p><button className="button button-primary" onClick={() => setView("today")} type="button">回到今日任务</button></div> : currentPlannedTarget ? <div className="recognition-card"><strong className="recognition-glyph">{currentPlannedTarget.character}</strong>{answerVisible ? <div className="recognition-answer"><p>{currentPlannedTarget.pinyin}</p><small>看到提示后，请选择“提示后认识”</small></div> : <p className="answer-hidden">拼音和答案默认隐藏</p>}<div className="outcome-grid"><button onClick={() => void recordPlannedOutcome("correct")} disabled={isLoading} type="button">认识</button><button onClick={() => { setAnswerVisible(true); }} className="hint-button" disabled={isLoading} type="button">查看提示</button><button onClick={() => void recordPlannedOutcome("hinted_correct")} disabled={!answerVisible || isLoading} type="button">提示后认识</button><button onClick={() => void recordPlannedOutcome("uncertain")} disabled={isLoading} type="button">不确定</button><button onClick={() => void recordPlannedOutcome("incorrect")} disabled={isLoading} type="button">不认识</button></div></div> : null}</section>
      ) : null}

      {view === "quick" ? (
        <section className="learning-workspace assessment-workspace"><header><div><p className="eyebrow">临时检查</p><h2>快速认字</h2></div><span>不会替代每日复习队列</span></header>{quickQuestion ? <div className="recognition-card"><strong className="recognition-glyph">{quickQuestion.character}</strong>{answerVisible ? <div className="recognition-answer"><p>{quickQuestion.pinyin}</p><small>{quickQuestion.simple_meaning}</small></div> : <p className="answer-hidden">答案默认隐藏</p>}<div className="outcome-grid"><button onClick={() => void recordQuickOutcome("correct")} type="button">认识</button><button className="hint-button" onClick={() => setAnswerVisible(true)} type="button">查看提示</button><button disabled={!answerVisible} onClick={() => void recordQuickOutcome("hinted_correct")} type="button">提示后认识</button><button onClick={() => void recordQuickOutcome("uncertain")} type="button">不确定</button><button onClick={() => void recordQuickOutcome("incorrect")} type="button">不认识</button></div></div> : <div className="empty-learning-state"><h3>暂无可检查的已学汉字</h3><button className="button button-secondary" onClick={() => setView("overview")} type="button">返回总览</button></div>}</section>
      ) : null}

      {view === "records" ? (
        <section className="learning-workspace"><header><div><p className="eyebrow">可追溯证据</p><h2>识字记录</h2></div><span>搜索、掌握状态和重点复习</span></header><form className="history-filters" onSubmit={(event) => { event.preventDefault(); void loadMasteryHistory(); }}><label>搜索<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="汉字或拼音" /></label><label>掌握状态<select value={level} onChange={(event) => setLevel(event.target.value as MasteryLevel | "")}><option value="">全部</option>{Object.entries(LEVEL_LABELS).map(([value, labelValue]) => <option key={value} value={value}>{labelValue}</option>)}</select></label><label className="priority-filter"><input type="checkbox" checked={priorityOnly} onChange={(event) => setPriorityOnly(event.target.checked)} />只看重点</label><button className="button button-secondary" type="submit">查询</button></form>{masteryHistory ? <div className="character-table-wrap"><table className="catalog-table"><thead><tr><th>字</th><th>拼音</th><th>状态</th><th>证据</th><th>操作</th></tr></thead><tbody>{masteryHistory.items.map((item) => <tr key={item.knowledge_point_id}><td className="character-cell">{item.character}{item.is_priority ? <span className="priority-badge static">重点</span> : null}</td><td>{item.pinyin}</td><td><span className={`mastery-pill ${item.mastery_level}`}>{LEVEL_LABELS[item.mastery_level]}</span></td><td>{item.correct_count} 认识 · {item.incorrect_count} 不认识</td><td><button className="table-action" onClick={() => void getCharacterMasteryDetail(childId, item.knowledge_point_id).then(setDetail)} type="button">详情</button>{family.current_role === "admin" ? <button className="table-action" onClick={() => void togglePriority(item.knowledge_point_id, !item.is_priority)} type="button">{item.is_priority ? "取消重点" : "设为重点"}</button> : null}</td></tr>)}</tbody></table></div> : isLoading ? <div className="center-state compact"><span className="loading-spinner" /></div> : null}{detail ? <div className="mastery-detail"><header><div><strong>{detail.state.character}</strong><div><h3>{detail.state.pinyin}</h3><span className={`mastery-pill ${detail.state.mastery_level}`}>{LEVEL_LABELS[detail.state.mastery_level]}</span></div></div><button onClick={() => setDetail(null)} type="button">关闭</button></header><div className="detail-stats"><span>认识 {detail.state.correct_count}</span><span>提示 {detail.state.hinted_correct_count}</span><span>不确定 {detail.state.uncertain_count}</span><span>不认识 {detail.state.incorrect_count}</span></div><ol>{detail.timeline.map((item) => <li key={item.id}><time>{formatTime(item.occurred_at)}</time><strong>{item.evidence_type === "learning" ? "学习" : "测评"}</strong><span>{item.value}</span><small>{item.response_time_ms == null ? "" : `${item.response_time_ms} ms`}</small></li>)}</ol></div> : null}</section>
      ) : null}

      {view === "assessments" ? (
        <section className="learning-workspace"><header><div><p className="eyebrow">真实测评证据</p><h2>测试历史</h2></div><span>每日复习 · 周度小挑战 · 月度识字检测</span></header>{isLoading ? <div className="center-state compact"><span className="loading-spinner" /></div> : history.length ? <div className="assessment-history-list">{history.map((item) => <button key={item.id} onClick={() => void openSessionDetail(item.id)} type="button"><div><strong>{SOURCE_LABELS[item.source]}</strong><span>{formatTime(item.started_at)}</span></div><div><span>{item.item_count} 项</span><span>认识 {item.correct}</span><span>提示 {item.hinted_correct}</span><span>不确定 {item.uncertain}</span><span>不认识 {item.incorrect}</span></div></button>)}</div> : <div className="empty-learning-state"><h3>还没有测试记录</h3><p>完成每日复习、周度或月度检测后会显示在这里。</p></div>}{session ? <div className="history-session-detail"><h3>{SOURCE_LABELS[session.source]} · {formatTime(session.started_at)}</h3><div className="target-chip-list">{session.targets.map((target) => <span key={target.knowledge_point_id}><strong>{target.character}</strong>{target.outcome ? OUTCOME_LABELS[target.outcome] : "未完成"}<small>{target.sampling_class}</small></span>)}</div></div> : null}</section>
      ) : null}

      {view === "settings" ? (
        <section className="learning-workspace"><header><div><p className="eyebrow">家长管理</p><h2>学习设置</h2></div><span>只有家庭管理员可以修改</span></header>{settings ? <div className="learning-settings-form"><label>每日最多新字<input type="number" min="0" max="20" value={settings.max_new_characters_per_day} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, max_new_characters_per_day: Number(event.target.value) })} /></label><label>每日复习容量<input type="number" min="1" max="100" value={settings.daily_review_capacity} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, daily_review_capacity: Number(event.target.value) })} /></label><label className="toggle-setting"><input type="checkbox" checked={settings.weekly_assessment_enabled} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, weekly_assessment_enabled: event.target.checked })} />开启周度小挑战</label><label className="toggle-setting"><input type="checkbox" checked={settings.monthly_assessment_enabled} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, monthly_assessment_enabled: event.target.checked })} />开启月度识字检测</label><label>时区<input value={settings.timezone} disabled={family.current_role !== "admin"} onChange={(event) => setSettings({ ...settings, timezone: event.target.value })} /></label>{family.current_role === "admin" ? <button className="button button-primary" onClick={() => void saveSettings()} disabled={isLoading} type="button">保存设置</button> : <p className="role-note">陪伴者可以学习和测评，但不能修改家庭学习设置。</p>}</div> : <div className="center-state compact"><span className="loading-spinner" /></div>}</section>
      ) : null}
    </section>
  );
}

export default function CharacterLearningPage() {
  return <ProtectedPage><CharacterLearningContent /></ProtectedPage>;
}
