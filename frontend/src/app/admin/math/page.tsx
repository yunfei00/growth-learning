"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminProtectedPage } from "@/components/admin-protected-page";
import {
  ApiClientError,
  getAdminMath,
  importMathFoundation,
  listAdminMath,
  type MathSkill,
  type MathSkillDetail,
  updateAdminMath,
} from "@/lib/api/client";

const DOMAIN_LABELS: Record<string, string> = {
  classification: "分类与配对",
  quantity: "数量与数数",
  number_symbol: "数字符号",
  comparison: "大小比较",
  sequence: "数序",
  composition: "分解组合",
  operation: "加减含义",
  pattern: "规律",
  geometry: "图形",
  spatial: "空间",
  measurement: "简单测量",
};

function AdminMathContent() {
  const [items, setItems] = useState<MathSkill[]>([]);
  const [selected, setSelected] = useState<MathSkillDetail | null>(null);
  const [domain, setDomain] = useState("");
  const [status, setStatus] = useState<"active" | "archived" | "">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [working, setWorking] = useState(false);

  const load = useCallback(async () => {
    try {
      const page = await listAdminMath({ domain, status, search, pageSize: 100 });
      setItems(page.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "数学内容加载失败");
    }
  }, [domain, search, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const open = async (item: MathSkill) => {
    try {
      setSelected(await getAdminMath(item.knowledge_point_id));
      setMessage("");
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "数学详情加载失败");
    }
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    setWorking(true);
    try {
      const updated = await updateAdminMath(selected.knowledge_point_id, {
        status: selected.status,
        title: selected.title,
        child_instruction: selected.child_instruction,
        parent_tip: selected.parent_tip,
        recommended_age_min: selected.recommended_age_min,
        recommended_age_max: selected.recommended_age_max,
      });
      setSelected(updated);
      setMessage("数学 Skill 已保存；canonical key、模板和儿童 mastery 均未被直接修改。");
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
      const result = await importMathFoundation();
      setMessage(`导入完成：${result.catalog_version}，${result.catalog_size} 个 Skill，${result.template_count} 个题目模板。`);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiClientError ? reason.message : "导入失败");
    } finally {
      setWorking(false);
    }
  };

  return <section className="admin-page admin-math-page">
    <header className="admin-page-header"><div><p className="eyebrow">内容管理</p><h2>数学</h2><p>维护能力型 Skill 与确定性题型；管理员不能修改孩子 mastery。</p></div><button className="button button-secondary" disabled={working} onClick={() => void runImport()} type="button">同步 math-foundation-v1</button></header>
    {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
    {message ? <p className="form-message form-success" role="status">{message}</p> : null}
    <form className="admin-filter-bar" onSubmit={(event) => { event.preventDefault(); void load(); }}><label><span>搜索</span><input onChange={(event) => setSearch(event.target.value)} placeholder="Skill、标题或 canonical key" value={search} /></label><label><span>领域</span><select onChange={(event) => setDomain(event.target.value)} value={domain}><option value="">全部</option>{Object.entries(DOMAIN_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label><span>状态</span><select onChange={(event) => setStatus(event.target.value as typeof status)} value={status}><option value="">全部</option><option value="active">启用</option><option value="archived">归档</option></select></label><button className="button button-primary" type="submit">筛选</button></form>
    <div className="admin-math-workspace">
      <div className="admin-math-list" role="list">{items.map((item) => <button className={selected?.knowledge_point_id === item.knowledge_point_id ? "selected" : ""} key={item.knowledge_point_id} onClick={() => void open(item)} role="listitem" type="button"><strong>{item.title}</strong><span>{DOMAIN_LABELS[item.domain]}</span><small>课程位置 {item.order_index + 1} · {item.template_count} 题型 · math-v1</small><em>{item.status === "active" ? "启用" : "归档"}</em></button>)}</div>
      {selected ? <form className="admin-math-editor" onSubmit={save}><header><div><p className="eyebrow">{DOMAIN_LABELS[selected.domain]} · #{selected.order_index + 1}</p><h3>{selected.title}</h3><code>{selected.canonical_key}</code></div><span>{selected.templates.length} 个模板</span></header><label>状态<select onChange={(event) => setSelected({ ...selected, status: event.target.value as "active" | "archived" })} value={selected.status}><option value="active">启用</option><option value="archived">归档</option></select></label><label>标题<input onChange={(event) => setSelected({ ...selected, title: event.target.value })} value={selected.title} /></label><label>儿童指令<textarea onChange={(event) => setSelected({ ...selected, child_instruction: event.target.value })} value={selected.child_instruction} /></label><label>家长提示<textarea onChange={(event) => setSelected({ ...selected, parent_tip: event.target.value })} value={selected.parent_tip} /></label><div className="admin-age-fields"><label>建议年龄下限<input min="0" onChange={(event) => setSelected({ ...selected, recommended_age_min: event.target.value ? Number(event.target.value) : null })} type="number" value={selected.recommended_age_min ?? ""} /></label><label>建议年龄上限<input min="0" onChange={(event) => setSelected({ ...selected, recommended_age_max: event.target.value ? Number(event.target.value) : null })} type="number" value={selected.recommended_age_max ?? ""} /></label></div><section className="admin-math-templates"><h4>题目模板</h4>{selected.templates.map((template) => <article key={template.id}><strong>{template.representation_type}</strong><code>{template.template_key}</code><small>{template.generator_version} · difficulty {template.difficulty}</small></article>)}</section><button className="button button-primary" disabled={working} type="submit">保存 Skill</button></form> : <div className="admin-empty-panel"><h3>选择一个数学 Skill</h3><p>可以查看领域、课程位置、题型与维护字段。</p></div>}
    </div>
  </section>;
}

export default function AdminMathPage() {
  return <AdminProtectedPage><AdminMathContent /></AdminProtectedPage>;
}
