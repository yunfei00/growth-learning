"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminProtectedPage } from "@/components/admin-protected-page";
import {
  ApiClientError,
  getAdminPinyin,
  importPinyinFoundation,
  listAdminPinyin,
  updateAdminPinyin,
  type PinyinItem,
  type PinyinItemDetail,
  type PinyinKind,
} from "@/lib/api/client";

const KIND_LABELS: Record<PinyinKind, string> = { initial: "声母", final: "韵母", tone: "声调", whole: "整体认读" };
const AUDIO_LABELS = { curated: "正式音频", tts_fallback: "TTS fallback", missing: "缺失" } as const;

function AdminPinyinContent() {
  const [items, setItems] = useState<PinyinItem[]>([]);
  const [selected, setSelected] = useState<PinyinItemDetail | null>(null);
  const [kind, setKind] = useState<PinyinKind | "">("");
  const [status, setStatus] = useState<"active" | "archived" | "">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  const load = useCallback(async () => {
    try {
      const page = await listAdminPinyin({ kind, status, search, pageSize: 100 });
      setItems(page.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "拼音内容加载失败");
    }
  }, [kind, search, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const open = async (item: PinyinItem) => {
    try {
      setSelected(await getAdminPinyin(item.knowledge_point_id));
      setMessage("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "拼音详情加载失败");
    }
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    setWorking(true);
    try {
      const updated = await updateAdminPinyin(selected.knowledge_point_id, {
        status: selected.status,
        pronunciation_cue: selected.pronunciation_cue,
        example_text: selected.example_text,
        example_pinyin: selected.example_pinyin,
        description: selected.description,
        parent_tip: selected.parent_tip,
        audio_key: selected.audio_key,
      });
      setSelected(updated);
      setMessage("拼音内容已保存；canonical key 和 KnowledgePoint ID 保持不变。");
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "保存失败");
    } finally {
      setWorking(false);
    }
  };

  const runImport = async () => {
    setWorking(true);
    try {
      const result = await importPinyinFoundation();
      setMessage(`导入完成：${result.catalog_version}，共 ${result.catalog_size} 项，新增 ${result.created}，跳过 ${result.skipped}。`);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "导入失败");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="admin-page admin-pinyin-page">
      <header className="admin-page-header"><div><p className="eyebrow">内容管理</p><h2>拼音</h2><p>维护正式拼音内容、发音线索和音频状态；不在这里修改儿童 mastery。</p></div><button className="button button-secondary" disabled={working} onClick={() => void runImport()} type="button">同步 pinyin-foundation-v1</button></header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}
      <form className="admin-filter-bar" onSubmit={(event) => { event.preventDefault(); void load(); }}>
        <label><span>搜索</span><input onChange={(event) => setSearch(event.target.value)} placeholder="符号、例词或 canonical key" value={search} /></label>
        <label><span>类型</span><select onChange={(event) => setKind(event.target.value as PinyinKind | "")} value={kind}><option value="">全部</option>{Object.entries(KIND_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label><span>状态</span><select onChange={(event) => setStatus(event.target.value as typeof status)} value={status}><option value="">全部</option><option value="active">启用</option><option value="archived">归档</option></select></label>
        <button className="button button-primary" type="submit">筛选</button>
      </form>
      <div className="admin-pinyin-workspace">
        <div className="admin-pinyin-list" role="list">
          {items.map((item) => <button className={selected?.knowledge_point_id === item.knowledge_point_id ? "selected" : ""} key={item.knowledge_point_id} onClick={() => void open(item)} role="listitem" type="button"><strong>{item.display_text}</strong><span>{KIND_LABELS[item.kind]}</span><span>顺序 {item.order_index + 1}</span><span className={`audio-${item.audio_status}`}>{AUDIO_LABELS[item.audio_status]}</span><small>{item.status === "active" ? "启用" : "归档"}</small></button>)}
        </div>
        {selected ? (
          <form className="admin-pinyin-editor" onSubmit={save}>
            <header><div><p className="eyebrow">{KIND_LABELS[selected.kind]} · #{selected.order_index + 1}</p><h3>{selected.display_text}</h3><code>{selected.canonical_key}</code></div><span className={`audio-${selected.audio.mode}`}>{AUDIO_LABELS[selected.audio.mode]}</span></header>
            <label>状态<select onChange={(event) => setSelected({ ...selected, status: event.target.value as "active" | "archived" })} value={selected.status}><option value="active">启用</option><option value="archived">归档</option></select></label>
            <label>发音提示<textarea onChange={(event) => setSelected({ ...selected, pronunciation_cue: event.target.value })} value={selected.pronunciation_cue ?? ""} /></label>
            <label>例词<input onChange={(event) => setSelected({ ...selected, example_text: event.target.value })} value={selected.example_text ?? ""} /></label>
            <label>例词拼音<input onChange={(event) => setSelected({ ...selected, example_pinyin: event.target.value })} value={selected.example_pinyin ?? ""} /></label>
            <label>儿童提示<textarea onChange={(event) => setSelected({ ...selected, description: event.target.value })} value={selected.description ?? ""} /></label>
            <label>家长提示<textarea onChange={(event) => setSelected({ ...selected, parent_tip: event.target.value })} value={selected.parent_tip ?? ""} /></label>
            <label>正式音频 object key<input onChange={(event) => setSelected({ ...selected, audio_key: event.target.value || null })} placeholder="pinyin/b.mp3" value={selected.audio_key ?? ""} /><small>为空时只使用安全中文 pronunciation cue；不会朗读 Latin 字母名。</small></label>
            <button className="button button-primary" disabled={working} type="submit">保存</button>
          </form>
        ) : <div className="admin-empty-panel"><h3>选择一个拼音项目</h3><p>右侧会显示适合该领域的维护字段。</p></div>}
      </div>
    </section>
  );
}

export default function AdminPinyinPage() {
  return <AdminProtectedPage><AdminPinyinContent /></AdminProtectedPage>;
}
