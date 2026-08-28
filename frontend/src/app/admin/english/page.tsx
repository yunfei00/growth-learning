"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { AdminProtectedPage } from "@/components/admin-protected-page";
import { EnglishVisualCard } from "@/components/english-visual";
import {
  ApiClientError,
  getAdminEnglish,
  importEnglishFoundation,
  listAdminEnglish,
  type EnglishItem,
  type EnglishItemDetail,
  type EnglishKind,
  updateAdminEnglish,
} from "@/lib/api/client";

const KIND_LABELS: Record<EnglishKind, string> = {
  word: "词汇",
  letter: "字母",
  phonics: "自然拼读",
  phrase: "短句",
};

function AdminEnglishContent() {
  const [items, setItems] = useState<EnglishItem[]>([]);
  const [selected, setSelected] = useState<EnglishItemDetail | null>(null);
  const [kind, setKind] = useState<EnglishKind | "">("");
  const [status, setStatus] = useState<"active" | "archived" | "">("");
  const [audioStatus, setAudioStatus] = useState<"curated" | "tts" | "phonics_missing" | "">("");
  const [visualStatus, setVisualStatus] = useState<"static" | "fallback" | "missing" | "">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  const load = useCallback(async () => {
    try {
      const page = await listAdminEnglish({ kind, status, audioStatus, visualStatus, search });
      setItems(page.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "英语内容加载失败");
    }
  }, [audioStatus, kind, search, status, visualStatus]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const open = async (item: EnglishItem) => {
    try {
      setSelected(await getAdminEnglish(item.knowledge_point_id));
      setMessage("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "英语详情加载失败");
    }
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    setWorking(true);
    try {
      const updated = await updateAdminEnglish(selected.knowledge_point_id, {
        status: selected.status,
        meaning_zh: selected.meaning_zh,
        child_hint_zh: selected.child_hint_zh,
        parent_tip: selected.parent_tip,
        example_text: selected.example_text,
        example_meaning_zh: selected.example_meaning_zh,
        category: selected.category,
        visual_type: selected.visual_type,
        image_key: selected.image_key,
        visual_key: selected.visual_key,
        audio_key: selected.audio_key,
      });
      setSelected(updated);
      setMessage("英语内容已保存；canonical key、练习证据和孩子 mastery 均未被直接修改。");
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
      const result = await importEnglishFoundation();
      setMessage(`同步完成：${result.catalog_version}，${result.catalog_size} 项内容，${result.practice_item_count} 个练习模板。`);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "同步失败");
    } finally {
      setWorking(false);
    }
  };

  return <section className="admin-page admin-english-page">
    <header className="admin-page-header"><div><p className="eyebrow">内容管理</p><h2>英语</h2><p>维护词汇、字母、phonics、短句与资源状态；不会在后台直接修改孩子 mastery。</p></div><button className="button button-secondary" disabled={working} onClick={() => void runImport()} type="button">同步 english-foundation-v1</button></header>
    {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
    {message ? <p className="form-message form-success" role="status">{message}</p> : null}
    <form className="admin-filter-bar" onSubmit={(event) => { event.preventDefault(); void load(); }}><label><span>搜索</span><input onChange={(event) => setSearch(event.target.value)} placeholder="内容、中文解释或 canonical key" value={search} /></label><label><span>类型</span><select onChange={(event) => setKind(event.target.value as typeof kind)} value={kind}><option value="">全部</option>{Object.entries(KIND_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label><span>状态</span><select onChange={(event) => setStatus(event.target.value as typeof status)} value={status}><option value="">全部</option><option value="active">启用</option><option value="archived">归档</option></select></label><label><span>音频</span><select onChange={(event) => setAudioStatus(event.target.value as typeof audioStatus)} value={audioStatus}><option value="">全部</option><option value="curated">正式音频</option><option value="tts">安全回退</option><option value="phonics_missing">Phonics 待补</option></select></label><label><span>视觉</span><select onChange={(event) => setVisualStatus(event.target.value as typeof visualStatus)} value={visualStatus}><option value="">全部</option><option value="static">静态图片</option><option value="fallback">回退视觉</option><option value="missing">缺少视觉</option></select></label><button className="button button-primary" type="submit">筛选</button></form>
    <div className="admin-english-workspace">
      <div className="admin-english-list" role="list">{items.map((item) => <button className={selected?.knowledge_point_id === item.knowledge_point_id ? "selected" : ""} key={item.knowledge_point_id} onClick={() => void open(item)} role="listitem" type="button"><EnglishVisualCard compact label={item.meaning_zh} visual={item.visual} /><span><strong>{item.text}</strong><small>{KIND_LABELS[item.kind]} · {item.category_label}</small><em>{item.audio.strategy} · {item.visual.visual_type}</em></span><b>{item.status === "active" ? "启用" : "归档"}</b></button>)}</div>
      {selected ? <form className="admin-english-editor" onSubmit={save}><header><EnglishVisualCard label={selected.meaning_zh} visual={selected.visual} /><div><p className="eyebrow">{KIND_LABELS[selected.kind]} · #{selected.order_index + 1}</p><h3>{selected.text}</h3><code>{selected.canonical_key}</code></div></header><label>状态<select onChange={(event) => setSelected({ ...selected, status: event.target.value as "active" | "archived" })} value={selected.status}><option value="active">启用</option><option value="archived">归档</option></select></label><label>中文解释<input onChange={(event) => setSelected({ ...selected, meaning_zh: event.target.value })} value={selected.meaning_zh} /></label><label>儿童提示<textarea onChange={(event) => setSelected({ ...selected, child_hint_zh: event.target.value })} value={selected.child_hint_zh} /></label><label>家长提示<textarea onChange={(event) => setSelected({ ...selected, parent_tip: event.target.value })} value={selected.parent_tip} /></label><label>例子<input onChange={(event) => setSelected({ ...selected, example_text: event.target.value || null })} value={selected.example_text ?? ""} /></label><label>例子中文<input onChange={(event) => setSelected({ ...selected, example_meaning_zh: event.target.value || null })} value={selected.example_meaning_zh ?? ""} /></label><label>分类<input onChange={(event) => setSelected({ ...selected, category: event.target.value })} value={selected.category} /></label><label>视觉类型<select onChange={(event) => setSelected({ ...selected, visual_type: event.target.value as EnglishItemDetail["visual_type"] })} value={selected.visual_type}><option value="static_image">静态图片</option><option value="icon">图标</option><option value="color_swatch">色块</option><option value="shape">图形</option><option value="emoji_fallback">Emoji 回退</option></select></label><label>图片路径<input onChange={(event) => setSelected({ ...selected, image_key: event.target.value || null })} placeholder="/english/visuals/cat.svg" value={selected.image_key ?? ""} /></label><label>视觉 key<input onChange={(event) => setSelected({ ...selected, visual_key: event.target.value || null })} value={selected.visual_key ?? ""} /></label><label>正式音频 object key<input onChange={(event) => setSelected({ ...selected, audio_key: event.target.value || null })} placeholder="english/en-US/cat.mp3" value={selected.audio_key ?? ""} /><small>Phonics 缺少正式音素时只播放安全示例词，绝不把字母名称当作音素。</small></label><section className="admin-english-practices"><h4>练习模板</h4>{selected.practices.map((practice) => <article key={practice.id}><strong>{practice.practice_kind}</strong><code>{practice.template_key}</code><small>{practice.generator_version}</small></article>)}</section><button className="button button-primary" disabled={working} type="submit">保存英语内容</button></form> : <div className="admin-empty-panel"><h3>选择一项英语内容</h3><p>可以查看资源策略、练习模板并维护人工内容。</p></div>}
    </div>
  </section>;
}

export default function AdminEnglishPage() {
  return <AdminProtectedPage><AdminEnglishContent /></AdminProtectedPage>;
}
