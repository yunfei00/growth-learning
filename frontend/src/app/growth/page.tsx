"use client";

import Link from "next/link";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ExportJob,
  type GrowthBookSummary,
  type GrowthCategory,
  type GrowthEvent,
  type GrowthReport,
  type GrowthReportSummary,
  createGrowthBook,
  createGrowthEvent,
  downloadFamilyExport,
  generateGrowthReport,
  getApiBaseUrl,
  getGrowthReport,
  listGrowthBooks,
  listGrowthEvents,
  listGrowthReports,
  requestFamilyExport,
  uploadGrowthMedia,
} from "@/lib/api/client";

const CATEGORY_LABELS: Record<string, string> = {
  learning: "学习",
  assessment: "测试",
  reading: "阅读",
  science: "科学",
  family: "家庭记录",
  original_words: "孩子原话",
  achievement: "里程碑",
  report: "报告",
};

function dateInput(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function GrowthArchive() {
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [events, setEvents] = useState<GrowthEvent[]>([]);
  const [reports, setReports] = useState<GrowthReportSummary[]>([]);
  const [books, setBooks] = useState<GrowthBookSummary[]>([]);
  const [selectedReport, setSelectedReport] = useState<GrowthReport | null>(null);
  const [category, setCategory] = useState<GrowthCategory | "">("");
  const [manualText, setManualText] = useState("");
  const [manualTitle, setManualTitle] = useState("");
  const [manualCategory, setManualCategory] = useState<"family" | "learning" | "reading" | "science">("family");
  const [manualFile, setManualFile] = useState<File | null>(null);
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [parentMessage, setParentMessage] = useState("");
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const now = useMemo(() => new Date(), []);
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const [periodType, setPeriodType] = useState<"monthly" | "yearly" | "custom">("monthly");
  const [periodStart, setPeriodStart] = useState(dateInput(monthStart));
  const [periodEnd, setPeriodEnd] = useState(dateInput(monthEnd));

  const load = useCallback(async () => {
    if (!activeChild || !family) return;
    try {
      const timeline = await listGrowthEvents(activeChild.id, {
        category: category || undefined,
      });
      setEvents(timeline.items);
      if (family.current_role === "admin") {
        const [reportItems, bookItems] = await Promise.all([
          listGrowthReports(activeChild.id),
          listGrowthBooks(activeChild.id),
        ]);
        setReports(reportItems);
        setBooks(bookItems);
      } else {
        setReports([]);
        setBooks([]);
      }
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "暂时无法加载成长档案");
    }
  }, [activeChild, category, family]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !family || !activeChild) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在整理成长档案…</p></section>;
  }

  const submitManual = async () => {
    if (!manualText.trim()) return;
    setSaving("manual");
    try {
      let event = await createGrowthEvent(activeChild.id, {
        occurred_at: new Date().toISOString(),
        title: manualTitle || null,
        text: manualText,
        event_type: "manual_growth_note",
        category: manualCategory,
      });
      if (manualFile) event = await uploadGrowthMedia(activeChild.id, event.id, manualFile);
      setManualText("");
      setManualTitle("");
      setManualFile(null);
      setEvents((current) => [event, ...current]);
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "成长记录保存失败");
    } finally {
      setSaving("");
    }
  };

  const createReport = async () => {
    setSaving("report");
    try {
      const report = await generateGrowthReport(activeChild.id, {
        period_type: periodType,
        period_start: periodStart,
        period_end: periodEnd,
      });
      setSelectedReport(report);
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "成长报告生成失败");
    } finally {
      setSaving("");
    }
  };

  const createBook = async () => {
    setSaving("book");
    try {
      await createGrowthBook(activeChild.id, {
        edition_type: "yearly",
        edition_key: String(now.getFullYear()),
        title: `《${now.getFullYear()} 成长册》`,
        selected_event_ids: selectedEvents,
        selected_media: [],
        parent_message: parentMessage || null,
      });
      setParentMessage("");
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "成长册保存失败");
    } finally {
      setSaving("");
    }
  };

  const startExport = async () => {
    setSaving("export");
    try {
      setExportJob(await requestFamilyExport(family.id));
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "家庭数据导出失败");
    } finally {
      setSaving("");
    }
  };

  const reportLearning = selectedReport?.metrics.learning as Record<string, unknown> | undefined;
  const reportReading = selectedReport?.metrics.reading as Record<string, unknown> | undefined;
  const reportScience = selectedReport?.metrics.science as Record<string, unknown> | undefined;

  return (
    <section className="growth-archive section-shell">
      <div className="dashboard-toolbar">
        <div><p className="eyebrow">Long-term Growth Archive</p><h1>成长档案</h1><p className="role-note">把学习、阅读、科学探索和家人记录放在同一条真实时间线上。</p></div>
        <ChildSwitcher activeChildId={activeChild.id} childOptions={children} onChange={setActiveChildId} />
      </div>
      {error ? <p className="form-message form-error">{error}</p> : null}

      <section className="growth-panel growth-capture">
        <div><p className="eyebrow">家庭原始记录</p><h2>+ 记录成长</h2><p>保留家人的原话；系统不会让 AI 改写它。</p></div>
        <div className="growth-capture-form">
          <input aria-label="记录标题" placeholder="标题（可选）" value={manualTitle} onChange={(event) => setManualTitle(event.target.value)} />
          <select aria-label="记录分类" value={manualCategory} onChange={(event) => setManualCategory(event.target.value as typeof manualCategory)}>
            <option value="family">家庭观察</option><option value="learning">学习</option><option value="reading">阅读</option><option value="science">科学</option>
          </select>
          <textarea aria-label="成长原话" placeholder="例如：今天第一次自己认出了路牌上的‘银行’。" value={manualText} onChange={(event) => setManualText(event.target.value)} />
          <input aria-label="成长媒体" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,audio/*" type="file" onChange={(event) => setManualFile(event.target.files?.[0] ?? null)} />
          <button className="button button-primary" disabled={!manualText.trim() || saving === "manual"} onClick={() => void submitManual()} type="button">{saving === "manual" ? "保存中…" : "保存成长记录"}</button>
        </div>
      </section>

      <section className="growth-panel">
        <div className="section-title-row"><div><p className="eyebrow">最近成长</p><h2>统一时间线</h2></div><select aria-label="时间线筛选" value={category} onChange={(event) => setCategory(event.target.value as GrowthCategory | "")}><option value="">全部</option>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div className="growth-timeline">
          {events.map((event) => (
            <article key={event.id}>
              <div className={`growth-dot growth-${event.category}`} />
              <div className="growth-event-card">
                <div><span>{CATEGORY_LABELS[event.category]}</span><time>{new Date(event.occurred_at).toLocaleString("zh-CN")}</time></div>
                <h3>{event.title}</h3><p>{event.body}</p>
                <small>{event.source_type === "system" ? "系统按真实证据生成" : `${event.actor_display_name || "家人"} 记录`}</small>
                {event.media.map((media) => <div className="growth-media" key={media.id}>{media.media_kind === "image" ? <Image alt={media.original_filename} height={320} src={`${getApiBaseUrl()}${media.content_url}`} unoptimized width={420} /> : media.media_kind === "video" ? <video controls src={`${getApiBaseUrl()}${media.content_url}`} /> : <audio controls src={`${getApiBaseUrl()}${media.content_url}`} />}</div>)}
                {event.source_url ? <Link href={event.source_url}>查看原始记录 →</Link> : null}
                {family.current_role === "admin" ? <label className="event-select"><input checked={selectedEvents.includes(event.id)} onChange={() => setSelectedEvents((current) => current.includes(event.id) ? current.filter((id) => id !== event.id) : [...current, event.id])} type="checkbox" />选入成长册</label> : null}
              </div>
            </article>
          ))}
          {events.length === 0 ? <p className="empty-storybook">这个筛选范围内还没有成长事件。</p> : null}
        </div>
      </section>

      {family.current_role === "admin" ? <>
        <section className="growth-panel report-builder">
          <div><p className="eyebrow">Evidence-backed report</p><h2>成长报告</h2><p>报告保存不可变快照；重新生成会创建新版本。</p></div>
          <div className="report-controls">
            <select aria-label="报告类型" value={periodType} onChange={(event) => setPeriodType(event.target.value as typeof periodType)}><option value="monthly">月度报告</option><option value="yearly">年度报告</option><option value="custom">自定义范围</option></select>
            <input aria-label="报告开始日期" type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
            <input aria-label="报告结束日期" type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
            <button className="button button-primary" disabled={saving === "report"} onClick={() => void createReport()} type="button">{saving === "report" ? "生成中…" : "生成真实报告"}</button>
          </div>
          <div className="report-history">{reports.map((report) => <button key={report.id} onClick={() => void getGrowthReport(activeChild.id, report.id).then(setSelectedReport)} type="button"><strong>{report.period_start} — {report.period_end}</strong><span>{report.period_type} · v{report.latest_version}</span></button>)}</div>
          {selectedReport ? <div className="report-preview"><h3>{selectedReport.period_start} — {selectedReport.period_end} 成长报告</h3><div className="report-metrics"><article><span>本期新接触</span><strong>{String(reportLearning?.newly_exposed ?? 0)}</strong></article><article><span>故事阅读</span><strong>{String(reportReading?.stories_read ?? 0)}</strong></article><article><span>科学实验</span><strong>{String(reportScience?.experiments_completed ?? 0)}</strong></article></div>{Object.entries(selectedReport.sections).map(([key, value]) => <p key={key}>{String(value)}</p>)}<small>算法 {selectedReport.policy_version} · 数据截止 {new Date(selectedReport.source_cutoff_at).toLocaleString("zh-CN")}</small></div> : null}
        </section>

        <section className="growth-panel book-builder">
          <div><p className="eyebrow">Memory, not a scorecard</p><h2>我的成长册</h2><p>从时间线勾选值得珍藏的事件，再写下家人的寄语。</p></div>
          <textarea aria-label="家长寄语" placeholder="写给孩子的一段话（可选）" value={parentMessage} onChange={(event) => setParentMessage(event.target.value)} />
          <button className="button button-primary" disabled={saving === "book"} onClick={() => void createBook()} type="button">{saving === "book" ? "保存中…" : `创建 ${now.getFullYear()} 成长册`}</button>
          <div className="book-list">{books.map((book) => <Link href={`/growth/book/${book.id}/print`} key={book.id}><strong>{book.title}</strong><span>v{book.latest_version} · 预览/打印 PDF</span></Link>)}</div>
        </section>

        <section className="growth-panel export-panel">
          <div><p className="eyebrow">Data portability</p><h2>家庭完整数据导出</h2><p>生成私有的 growth-learning-export-v1 ZIP，包含 JSON、CSV 和媒体；绝不包含密码、Token 或服务密钥。</p></div>
          <button className="button button-primary" disabled={saving === "export"} onClick={() => void startExport()} type="button">{saving === "export" ? "正在安全打包…" : "请求家庭数据导出"}</button>
          {exportJob ? <div className="export-result"><strong>{exportJob.status === "completed" ? "导出已完成" : exportJob.status}</strong><span>{exportJob.size_bytes ? `${Math.ceil(exportJob.size_bytes / 1024)} KB` : ""}</span><small>校验：{exportJob.checksum_sha256?.slice(0, 16)}… · 到期后不可下载</small>{exportJob.download_url ? <button className="button button-secondary" onClick={() => void downloadFamilyExport(exportJob)} type="button">下载私有 ZIP</button> : null}</div> : null}
        </section>
      </> : <section className="growth-panel"><h2>家庭陪伴者权限</h2><p>你可以查看时间线并记录成长；完整报告、成长册和家庭导出由家庭管理员管理。</p></section>}
    </section>
  );
}

export default function GrowthPage() {
  return <ProtectedPage><GrowthArchive /></ProtectedPage>;
}
