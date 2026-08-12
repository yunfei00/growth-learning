"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type CharacterMasteryDetail,
  type CharacterMasteryPage,
  type CharacterMasterySummary,
  type CharacterRecommendation,
  type MasteryLevel,
  createAssessmentSession,
  createLearningSession,
  getCharacterMasteryDetail,
  getCharacterMasterySummary,
  getCharacterRecommendations,
  listCharacterMastery,
  updateCharacterPriority,
} from "@/lib/api/client";

type View = "overview" | "new" | "assessment" | "history";
type AssessmentOutcome = "correct" | "hinted_correct" | "uncertain" | "incorrect";

const LEVEL_LABELS: Record<MasteryLevel, string> = {
  unlearned: "未学习",
  introduced: "已接触",
  recognizing: "正在认识",
  proficient: "基本掌握",
  stable: "稳定掌握",
};

function formatTime(value: string | null): string {
  if (!value) return "暂无";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
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
  const [view, setView] = useState<View>("overview");
  const [summary, setSummary] = useState<CharacterMasterySummary | null>(null);
  const [recommendations, setRecommendations] = useState<CharacterRecommendation[]>([]);
  const [assessmentIndex, setAssessmentIndex] = useState(0);
  const [answers, setAnswers] = useState<
    Array<{
      knowledge_point_id: string;
      outcome: AssessmentOutcome;
      response_time_ms: number;
      hint_used?: boolean;
    }>
  >([]);
  const [answerVisible, setAnswerVisible] = useState(false);
  const questionStartedAt = useRef(0);
  const [history, setHistory] = useState<CharacterMasteryPage | null>(null);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<MasteryLevel | "">("");
  const [priorityOnly, setPriorityOnly] = useState(false);
  const [detail, setDetail] = useState<CharacterMasteryDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const childId = activeChild?.id ?? "";

  const loadSummary = useCallback(async () => {
    if (!childId) return;
    try {
      const value = await getCharacterMasterySummary(childId);
      setSummary(value);
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError ? requestError.message : "识字概览加载失败",
      );
    }
  }, [childId]);

  const loadHistory = useCallback(
    async (page = 1) => {
      if (!childId) return;
      setIsLoading(true);
      setError("");
      try {
        setHistory(
          await listCharacterMastery(childId, {
            search,
            masteryLevel: level || undefined,
            priority: priorityOnly ? true : undefined,
            page,
            pageSize: 12,
          }),
        );
      } catch (requestError) {
        setError(
          requestError instanceof ApiClientError ? requestError.message : "学习记录加载失败",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [childId, level, priorityOnly, search],
  );

  useEffect(() => {
    if (status === "ready" && (!family || !activeChild)) router.replace("/onboarding");
  }, [activeChild, family, router, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSummary(), 0);
    return () => window.clearTimeout(timer);
  }, [loadSummary]);

  const switchChild = (nextChildId: string) => {
    setView("overview");
    setSummary(null);
    setRecommendations([]);
    setHistory(null);
    setDetail(null);
    setMessage("");
    setError("");
    setActiveChildId(nextChildId);
  };

  const startNewLearning = async () => {
    if (!childId) return;
    setView("new");
    setIsLoading(true);
    setError("");
    setMessage("");
    try {
      setRecommendations(await getCharacterRecommendations(childId, "new", 5));
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "新字加载失败");
    } finally {
      setIsLoading(false);
    }
  };

  const completeLearning = async () => {
    if (!childId || recommendations.length === 0) return;
    setIsLoading(true);
    setError("");
    try {
      await createLearningSession(
        childId,
        recommendations.map((item) => item.id),
      );
      setMessage(`已保存 ${recommendations.length} 条学习证据`);
      setRecommendations([]);
      await loadSummary();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "学习记录保存失败");
    } finally {
      setIsLoading(false);
    }
  };

  const startAssessment = async () => {
    if (!childId) return;
    setView("assessment");
    setIsLoading(true);
    setError("");
    setMessage("");
    try {
      const items = await getCharacterRecommendations(childId, "assessment", 5);
      setRecommendations(items);
      setAssessmentIndex(0);
      setAnswers([]);
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "认读题目加载失败");
    } finally {
      setIsLoading(false);
    }
  };

  const recordOutcome = async (outcome: AssessmentOutcome) => {
    const current = recommendations[assessmentIndex];
    if (!current || !childId) return;
    const nextAnswers = [
      ...answers,
      {
        knowledge_point_id: current.id,
        outcome,
        response_time_ms: Math.max(0, Math.round(performance.now() - questionStartedAt.current)),
        hint_used: answerVisible,
      },
    ];
    setAnswers(nextAnswers);
    if (assessmentIndex + 1 < recommendations.length) {
      setAssessmentIndex((value) => value + 1);
      setAnswerVisible(false);
      questionStartedAt.current = performance.now();
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      await createAssessmentSession(childId, nextAnswers);
      setRecommendations([]);
      setMessage(`本次认读已保存 ${nextAnswers.length} 条原始结果`);
      await loadSummary();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "认读结果保存失败");
    } finally {
      setIsLoading(false);
    }
  };

  const openHistory = async () => {
    setView("history");
    setMessage("");
    setDetail(null);
    await loadHistory();
  };

  const openDetail = async (knowledgePointId: string) => {
    if (!childId) return;
    setIsLoading(true);
    setError("");
    try {
      setDetail(await getCharacterMasteryDetail(childId, knowledgePointId));
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "详情加载失败");
    } finally {
      setIsLoading(false);
    }
  };

  const togglePriority = async (knowledgePointId: string, value: boolean) => {
    if (!childId) return;
    setIsLoading(true);
    setError("");
    try {
      await updateCharacterPriority(childId, knowledgePointId, value);
      await Promise.all([loadHistory(history?.page ?? 1), loadSummary()]);
      if (detail?.state.knowledge_point_id === knowledgePointId) {
        setDetail(await getCharacterMasteryDetail(childId, knowledgePointId));
      }
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "优先级更新失败");
    } finally {
      setIsLoading(false);
    }
  };

  if (status === "idle" || status === "loading") {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在准备孩子的识字空间…</p>
      </section>
    );
  }
  if (status === "error") {
    return (
      <section className="center-state section-shell">
        <h1>暂时无法进入识字学习</h1>
        <p>{householdError}</p>
        <button className="button button-primary" onClick={() => void refresh()} type="button">
          重新加载
        </button>
      </section>
    );
  }
  if (!family || !activeChild) return null;

  const childName = activeChild.nickname || activeChild.display_name;
  const currentQuestion = recommendations[assessmentIndex];

  return (
    <section className="character-learning-page section-shell">
      <header className="learning-page-header">
        <div>
          <p className="eyebrow">长期识字档案</p>
          <h1>{childName}的识字学习</h1>
          <p>每次学习和认读都会保留原始记录，掌握度可随时重算。</p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={switchChild}
        />
      </header>

      <nav className="learning-tabs" aria-label="识字学习功能">
        <button className={view === "overview" ? "active" : ""} onClick={() => setView("overview")} type="button">
          概览
        </button>
        <button className={view === "new" ? "active" : ""} onClick={() => void startNewLearning()} type="button">
          学习新字
        </button>
        <button className={view === "assessment" ? "active" : ""} onClick={() => void startAssessment()} type="button">
          快速认读
        </button>
        <button className={view === "history" ? "active" : ""} onClick={() => void openHistory()} type="button">
          学习记录
        </button>
      </nav>

      {error ? <p className="form-message form-error learning-message" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success learning-message" role="status">{message}</p> : null}

      {view === "overview" ? (
        <div className="learning-overview">
          {summary ? (
            <div className="mastery-metric-grid">
              {(
                [
                  ["未学习", summary.unlearned],
                  ["已接触", summary.introduced],
                  ["正在认识", summary.recognizing],
                  ["基本掌握", summary.proficient],
                  ["稳定掌握", summary.stable],
                ] as const
              ).map(([label, value]) => (
                <article key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>字</small>
                </article>
              ))}
            </div>
          ) : (
            <div className="center-state compact"><span className="loading-spinner" /><p>正在读取真实掌握度…</p></div>
          )}
          <div className="learning-cta-grid">
            <button className="learning-cta" onClick={() => void startNewLearning()} type="button">
              <span>01</span><strong>学习 5 个新字</strong><small>按知识库顺序选择未学习且启用的字</small>
            </button>
            <button className="learning-cta" onClick={() => void startAssessment()} type="button">
              <span>02</span><strong>开始快速认读</strong><small>答案先隐藏，记录四种真实结果和反应时间</small>
            </button>
          </div>
        </div>
      ) : null}

      {view === "new" ? (
        <section className="learning-workspace">
          <header><div><p className="eyebrow">新字学习</p><h2>本次 5 字</h2></div><span>只选择未出现过学习记录的启用汉字</span></header>
          {isLoading ? <div className="center-state compact"><span className="loading-spinner" /><p>正在准备新字…</p></div> : recommendations.length > 0 ? (
            <>
              <div className="new-character-grid">
                {recommendations.map((item) => (
                  <article key={item.id}>
                    <strong>{item.character}</strong><p className="character-pinyin">{item.pinyin}</p>
                    <p>{item.common_words.join(" · ") || "暂无常用词"}</p>
                    <small>{item.simple_meaning || "暂无简释"}</small>
                    {item.is_priority ? <span className="priority-badge">优先</span> : null}
                  </article>
                ))}
              </div>
              <button className="button button-primary workspace-submit" disabled={isLoading} onClick={() => void completeLearning()} type="button">完成本次学习并保存记录</button>
            </>
          ) : <div className="empty-learning-state"><h3>暂无未学习的新字</h3><p>可以前往快速认读，继续积累真实测评证据。</p></div>}
        </section>
      ) : null}

      {view === "assessment" ? (
        <section className="learning-workspace assessment-workspace">
          <header><div><p className="eyebrow">快速认读</p><h2>先看字，再判断</h2></div>{currentQuestion ? <span>{assessmentIndex + 1} / {recommendations.length}</span> : null}</header>
          {isLoading ? <div className="center-state compact"><span className="loading-spinner" /><p>正在保存认读结果…</p></div> : currentQuestion ? (
            <div className="recognition-card">
              <strong className="recognition-glyph">{currentQuestion.character}</strong>
              {answerVisible ? <div className="recognition-answer"><p>{currentQuestion.pinyin}</p><p>{currentQuestion.common_words.join(" · ")}</p><small>{currentQuestion.simple_meaning}</small></div> : <p className="answer-hidden">读音、词语和释义已隐藏</p>}
              <div className="outcome-grid">
                {!answerVisible ? <>
                  <button onClick={() => void recordOutcome("correct")} type="button">认识</button>
                  <button onClick={() => void recordOutcome("uncertain")} type="button">不确定</button>
                  <button onClick={() => void recordOutcome("incorrect")} type="button">不认识</button>
                  <button className="hint-button" onClick={() => setAnswerVisible(true)} type="button">查看提示</button>
                </> : <>
                  <button onClick={() => void recordOutcome("hinted_correct")} type="button">提示后认识</button>
                  <button onClick={() => void recordOutcome("incorrect")} type="button">提示后仍不认识</button>
                </>}
              </div>
            </div>
          ) : <div className="empty-learning-state"><h3>还没有可认读的已学汉字</h3><p>先完成一次新字学习，再回来快速认读。</p><button className="button button-primary" onClick={() => void startNewLearning()} type="button">去学习新字</button></div>}
        </section>
      ) : null}

      {view === "history" ? (
        <section className="learning-workspace history-workspace">
          <header><div><p className="eyebrow">真实档案</p><h2>学习记录</h2></div><span>掌握度是派生结果，原始证据始终保留</span></header>
          <form className="history-filters" onSubmit={(event) => { event.preventDefault(); void loadHistory(); }}>
            <label><span>搜索汉字或拼音</span><input onChange={(event) => setSearch(event.target.value)} value={search} /></label>
            <label><span>掌握度</span><select onChange={(event) => setLevel(event.target.value as MasteryLevel | "")} value={level}><option value="">全部</option>{Object.entries(LEVEL_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label className="priority-filter"><input checked={priorityOnly} onChange={(event) => setPriorityOnly(event.target.checked)} type="checkbox" /><span>只看优先字</span></label>
            <button className="button button-secondary" type="submit">筛选</button>
          </form>
          {isLoading && !history ? <div className="center-state compact"><span className="loading-spinner" /></div> : history ? <>
            <div className="catalog-table-wrap"><table className="catalog-table mastery-table"><thead><tr><th>字</th><th>拼音</th><th>掌握度</th><th>证据</th><th>优先</th><th>操作</th></tr></thead><tbody>{history.items.map((item) => <tr key={item.knowledge_point_id}><td className="character-glyph">{item.character}</td><td>{item.pinyin}</td><td><span className={`mastery-pill ${item.mastery_level}`}>{LEVEL_LABELS[item.mastery_level]}</span></td><td>学习 {item.first_introduced_at ? 1 : 0} · 测评 {item.correct_count + item.hinted_correct_count + item.uncertain_count + item.incorrect_count}</td><td>{item.is_priority ? "是" : "否"}</td><td><div className="table-actions"><button onClick={() => void openDetail(item.knowledge_point_id)} type="button">详情</button>{family.current_role === "admin" ? <button disabled={isLoading} onClick={() => void togglePriority(item.knowledge_point_id, !item.is_priority)} type="button">{item.is_priority ? "取消优先" : "设为优先"}</button> : null}</div></td></tr>)}</tbody></table></div>
            <div className="pagination"><span>共 {history.total} 个汉字</span><div><button disabled={history.page <= 1} onClick={() => void loadHistory(history.page - 1)} type="button">上一页</button><span>{history.page} / {history.pages}</span><button disabled={history.page >= history.pages} onClick={() => void loadHistory(history.page + 1)} type="button">下一页</button></div></div>
          </> : null}
          {detail ? <div className="mastery-detail"><header><div><strong>{detail.state.character}</strong><span>{detail.state.pinyin}</span></div><button onClick={() => setDetail(null)} type="button">关闭</button></header><div className="detail-stats"><span>{LEVEL_LABELS[detail.state.mastery_level]}</span><span>得分 {detail.state.mastery_score.toFixed(2)}</span><span>最近测评 {formatTime(detail.state.last_assessed_at)}</span></div><ol>{detail.timeline.length > 0 ? detail.timeline.map((item) => <li key={item.id}><span>{item.evidence_type === "learning" ? "学习" : "测评"}</span><strong>{item.value}</strong><time>{formatTime(item.occurred_at)}</time>{item.response_time_ms !== null ? <small>{item.response_time_ms} ms</small> : null}</li>) : <li>暂无证据记录</li>}</ol></div> : null}
        </section>
      ) : null}
    </section>
  );
}

export default function CharacterLearningPage() {
  return <ProtectedPage><CharacterLearningContent /></ProtectedPage>;
}
