"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  type AdminKnowledgePage,
  type AdminKnowledgePoint,
  ApiClientError,
  createAdminKnowledge,
  getAdminKnowledge,
  type KnowledgeType,
  listAdminKnowledge,
  type Subject,
} from "@/lib/api/client";

const SUBJECT_LABELS: Record<Subject, string> = {
  chinese: "语文",
  math: "数学",
  english: "英语",
  science: "科学",
};

const TYPES_BY_SUBJECT: Record<Subject, KnowledgeType[]> = {
  chinese: ["pinyin_initial", "pinyin_final", "pinyin_tone", "pinyin_syllable"],
  math: ["math_skill"],
  english: ["english_letter", "english_word", "english_phonics"],
  science: ["science_concept"],
};

const TYPE_LABELS: Record<KnowledgeType, string> = {
  chinese_character: "汉字",
  pinyin_initial: "声母",
  pinyin_final: "韵母",
  pinyin_tone: "声调",
  pinyin_syllable: "拼音音节",
  math_skill: "数学能力点",
  english_letter: "英文字母",
  english_word: "英语单词",
  english_phonics: "自然拼读",
  science_concept: "科学概念",
};

export default function AdminKnowledgePage() {
  const [result, setResult] = useState<AdminKnowledgePage | null>(null);
  const [subject, setSubject] = useState<Subject | "">("");
  const [type, setType] = useState<KnowledgeType | "">("");
  const [status, setStatus] = useState<"active" | "archived" | "">("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AdminKnowledgePoint | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createSubject, setCreateSubject] = useState<Subject>("math");
  const [createType, setCreateType] = useState<KnowledgeType>("math_skill");
  const [title, setTitle] = useState("");
  const [canonicalKey, setCanonicalKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setResult(await listAdminKnowledge({ subject, type, status, search, page }));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "知识点加载失败");
    }
  }, [page, search, status, subject, type]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const changeCreateSubject = (value: Subject) => {
    setCreateSubject(value);
    setCreateType(TYPES_BY_SUBJECT[value][0]);
  };

  const submitCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const created = await createAdminKnowledge({
        subject: createSubject,
        type: createType,
        title: title.trim(),
        canonical_key: canonicalKey.trim(),
        source_type: "manual",
      });
      setNotice(`“${created.title}”已创建。掌握度策略：${created.mastery_projection_status === "configured" ? "已配置" : "尚未配置"}。`);
      setTitle("");
      setCanonicalKey("");
      setShowCreate(false);
      setSelected(created);
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "知识点创建失败");
    } finally {
      setSaving(false);
    }
  };

  const openDetail = async (id: string) => {
    try {
      setSelected(await getAdminKnowledge(id));
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "知识点详情加载失败");
    }
  };

  const availableFilterTypes = subject
    ? (["chinese_character", ...TYPES_BY_SUBJECT[subject]] as KnowledgeType[])
    : (Object.keys(TYPE_LABELS) as KnowledgeType[]);

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="eyebrow">Canonical knowledge</p>
          <h2>跨学科知识点</h2>
          <p>知识定义与孩子学习证据分离；“未配置”不会被解释为未学习。</p>
        </div>
        <button className="button button-primary" onClick={() => setShowCreate((value) => !value)}>
          {showCreate ? "收起" : "新建知识点"}
        </button>
      </header>

      {showCreate ? (
        <form className="admin-filter-bar" onSubmit={(event) => void submitCreate(event)}>
          <label><span>学科</span><select value={createSubject} onChange={(event) => changeCreateSubject(event.target.value as Subject)}>{(Object.keys(SUBJECT_LABELS) as Subject[]).map((item) => <option key={item} value={item}>{SUBJECT_LABELS[item]}</option>)}</select></label>
          <label><span>类型</span><select value={createType} onChange={(event) => setCreateType(event.target.value as KnowledgeType)}>{TYPES_BY_SUBJECT[createSubject].map((item) => <option key={item} value={item}>{TYPE_LABELS[item]}</option>)}</select></label>
          <label><span>标题</span><input required maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label><span>稳定键</span><input required placeholder="math:add-within-10" value={canonicalKey} onChange={(event) => setCanonicalKey(event.target.value)} /></label>
          <button className="button button-primary" disabled={saving}>{saving ? "保存中…" : "保存"}</button>
        </form>
      ) : null}

      <form className="admin-filter-bar" onSubmit={submitSearch}>
        <label><span>学科</span><select value={subject} onChange={(event) => { setSubject(event.target.value as Subject | ""); setType(""); setPage(1); }}><option value="">全部学科</option>{(Object.keys(SUBJECT_LABELS) as Subject[]).map((item) => <option key={item} value={item}>{SUBJECT_LABELS[item]}</option>)}</select></label>
        <label><span>类型</span><select value={type} onChange={(event) => { setType(event.target.value as KnowledgeType | ""); setPage(1); }}><option value="">全部类型</option>{availableFilterTypes.map((item) => <option key={item} value={item}>{TYPE_LABELS[item]}</option>)}</select></label>
        <label><span>状态</span><select value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="">全部状态</option><option value="active">启用</option><option value="archived">归档</option></select></label>
        <label><span>标题或稳定键</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} /></label>
        <button className="button button-secondary">搜索</button>
      </form>

      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {notice ? <p className="form-message form-success">{notice}</p> : null}

      <div className="admin-table-wrap">
        <table className="admin-data-table">
          <thead><tr><th>知识点</th><th>学科 / 类型</th><th>掌握度投影</th><th>证据</th><th>操作</th></tr></thead>
          <tbody>{result?.items.map((item) => <tr key={item.id}>
            <td className="admin-primary-cell"><strong>{item.title}</strong><small>{item.canonical_key}</small></td>
            <td><strong>{SUBJECT_LABELS[item.subject]}</strong><small>{TYPE_LABELS[item.type]}</small></td>
            <td><span className={`status-pill ${item.mastery_projection_status === "configured" ? "active" : "suspended"}`}>{item.mastery_projection_status === "configured" ? item.mastery_policy_key : "未配置"}</span></td>
            <td>{item.learning_evidence_count} 学习 / {item.assessment_evidence_count} 测试</td>
            <td><button className="button button-secondary" type="button" onClick={() => void openDetail(item.id)}>详情</button></td>
          </tr>)}</tbody>
        </table>
        {result?.items.length === 0 ? <p className="empty-note">当前筛选下没有知识点；系统不会自动制造演示内容。</p> : null}
      </div>

      {result && result.pages > 1 ? <nav className="pagination-bar" aria-label="知识点分页"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button><span>第 {page} / {result.pages} 页 · 共 {result.total} 项</span><button disabled={page >= result.pages} onClick={() => setPage((value) => value + 1)}>下一页</button></nav> : null}

      {selected ? <aside className="catalog-provenance-card" aria-label="知识点详情"><div><span>标题</span><strong>{selected.title}</strong></div><div><span>学科</span><strong>{SUBJECT_LABELS[selected.subject]}</strong></div><div><span>类型</span><strong>{TYPE_LABELS[selected.type]}</strong></div><div><span>稳定键</span><strong>{selected.canonical_key}</strong></div><div><span>掌握度策略</span><strong>{selected.mastery_policy_key ?? "未配置"}</strong></div><div><span>孩子状态投影</span><strong>{selected.child_state_count}</strong></div></aside> : null}
    </section>
  );
}
