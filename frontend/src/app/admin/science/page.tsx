"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ApiClientError,
  type ScienceExperiment,
  type ScienceExperimentPage,
  type ScienceExperimentStatus,
  importStarterScience,
  listAdminScienceExperiments,
  updateAdminScienceExperiment,
} from "@/lib/api/client";

export default function AdminSciencePage() {
  const [catalog, setCatalog] = useState<ScienceExperimentPage | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ScienceExperimentStatus | "">("");
  const [selected, setSelected] = useState<ScienceExperiment | null>(null);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setCatalog(await listAdminScienceExperiments({ search: search || undefined, status: status || undefined })); setError(""); }
    catch (reason) { setError(reason instanceof ApiClientError ? reason.message : "无法加载实验目录"); }
  }, [search, status]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 250); return () => window.clearTimeout(timer); }, [load]);
  const importStarter = async () => { setWorking(true); try { const report = await importStarterScience(); setMessage(`导入完成：新增 ${report.created}，更新 ${report.updated}，跳过 ${report.skipped}`); await load(); } catch (reason) { setError(reason instanceof ApiClientError ? reason.message : "导入失败"); } finally { setWorking(false); } };
  const save = async () => { if (!selected) return; setWorking(true); try { const updated = await updateAdminScienceExperiment(selected.id, { title: selected.title, description: selected.description, age_min: selected.age_min, age_max: selected.age_max, difficulty: selected.difficulty, estimated_duration_minutes: selected.estimated_duration_minutes, guiding_question: selected.guiding_question, expected_phenomenon: selected.expected_phenomenon, child_friendly_explanation: selected.child_friendly_explanation, parent_scientific_explanation: selected.parent_scientific_explanation, safety_notes: selected.safety_notes, common_failure_reasons: selected.common_failure_reasons, follow_up_questions: selected.follow_up_questions, likely_child_questions: selected.likely_child_questions, steps: selected.steps, status: selected.status }); setSelected(updated); setMessage(`已保存不可变版本 ${updated.content_version}`); await load(); } catch (reason) { setError(reason instanceof ApiClientError ? reason.message : "保存失败"); } finally { setWorking(false); } };
  return <section className="admin-page">
    <header className="admin-page-header"><div><p className="eyebrow">Knowledge catalog</p><h2>科学实验目录</h2><p>系统模板可版本化、可停用，不物理删除孩子已经做过的内容。</p></div><button className="button button-primary" disabled={working} onClick={() => void importStarter()} type="button">导入 Starter 实验</button></header>
    {error ? <p className="form-message form-error">{error}</p> : null}{message ? <p className="form-message form-success">{message}</p> : null}
    <div className="admin-science-filters"><input placeholder="搜索标题或说明" value={search} onChange={(event) => setSearch(event.target.value)} /><select value={status} onChange={(event) => setStatus(event.target.value as ScienceExperimentStatus | "")}><option value="">全部状态</option><option value="enabled">启用</option><option value="draft">草稿</option><option value="archived">已归档</option></select><span>共 {catalog?.total ?? 0} 个模板</span></div>
    <div className="admin-science-layout"><div className="admin-science-list">{catalog?.items.map((item) => <button className={selected?.id === item.id ? "selected" : ""} key={item.id} onClick={() => setSelected(item)} type="button"><strong>{item.title}</strong><span>{item.age_min}–{item.age_max ?? "不限"} 岁 · {item.estimated_duration_minutes} 分钟</span><small>{item.status} · v{item.content_version}</small></button>)}</div>
      {selected ? <form className="science-editor" onSubmit={(event) => { event.preventDefault(); void save(); }}><h3>编辑实验模板</h3><label>标题<input value={selected.title} onChange={(event) => setSelected({ ...selected, title: event.target.value })} /></label><label>引导问题<textarea value={selected.guiding_question} onChange={(event) => setSelected({ ...selected, guiding_question: event.target.value })} /></label><label>儿童解释<textarea value={selected.child_friendly_explanation} onChange={(event) => setSelected({ ...selected, child_friendly_explanation: event.target.value })} /></label><label>家长科学解释<textarea value={selected.parent_scientific_explanation} onChange={(event) => setSelected({ ...selected, parent_scientific_explanation: event.target.value })} /></label><label>状态<select value={selected.status} onChange={(event) => setSelected({ ...selected, status: event.target.value as ScienceExperimentStatus })}><option value="enabled">启用</option><option value="draft">草稿</option><option value="archived">归档</option></select></label><button className="button button-primary" disabled={working} type="submit">{working ? "保存中…" : "保存为新版本"}</button></form> : <div className="center-state compact"><p>选择一个实验进行编辑。</p></div>}
    </div>
  </section>;
}
