"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type ExperimentSessionPage,
  type FamilyMaterial,
  type ScienceRecommendation,
  getFamilyMaterials,
  listExperimentSessions,
  listScienceRecommendations,
  updateFamilyMaterials,
} from "@/lib/api/client";

const DIFFICULTY = { intro: "启蒙", explore: "探索", advanced: "进阶" } as const;

function ScienceHub() {
  const { status, family, children, activeChild, setActiveChildId } = useActiveChild();
  const [recommendations, setRecommendations] = useState<ScienceRecommendation[]>([]);
  const [history, setHistory] = useState<ExperimentSessionPage | null>(null);
  const [materials, setMaterials] = useState<FamilyMaterial[]>([]);
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!activeChild || !family) return;
    try {
      const [recommended, sessions, inventory] = await Promise.all([
        listScienceRecommendations(activeChild.id),
        listExperimentSessions(activeChild.id),
        getFamilyMaterials(family.id),
      ]);
      setRecommendations(recommended);
      setHistory(sessions);
      setMaterials(inventory);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "暂时无法加载科学实验室");
    }
  }, [activeChild, family]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !family || !activeChild) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在准备周末科学实验室…</p></section>;
  }

  const saveInventory = async () => {
    setSaving(true);
    try {
      setMaterials(await updateFamilyMaterials(
        family.id,
        materials.map((item) => ({ material_id: item.material.id, is_owned: item.is_owned })),
      ));
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "材料清单保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="science-hub section-shell">
      <div className="dashboard-toolbar">
        <div><p className="eyebrow">Weekend Science Lab</p><h1>周末科学实验室</h1><p className="role-note">从真实提问、预测和观察开始，不给孩子打虚假的科学能力分数。</p></div>
        <ChildSwitcher activeChildId={activeChild.id} childOptions={children} onChange={setActiveChildId} />
      </div>
      {error ? <p className="form-message form-error">{error}</p> : null}

      <section className="science-panel">
        <div className="section-title-row"><div><p className="eyebrow">本周推荐</p><h2>适合 {activeChild.nickname || activeChild.display_name} 的实验</h2></div><button className="button button-secondary" type="button" onClick={() => setInventoryOpen(!inventoryOpen)}>家庭材料清单</button></div>
        {inventoryOpen ? (
          <div className="material-inventory">
            <p>勾选家中常备材料，推荐会优先选择现在就能做的实验。</p>
            <div>{materials.map((item) => <label key={item.material.id}><input type="checkbox" checked={item.is_owned} disabled={family.current_role !== "admin"} onChange={() => setMaterials((current) => current.map((row) => row.material.id === item.material.id ? { ...row, is_owned: !row.is_owned } : row))} />{item.material.name}</label>)}</div>
            {family.current_role === "admin" ? <button className="button button-primary" disabled={saving} type="button" onClick={() => void saveInventory()}>{saving ? "保存中…" : "保存材料清单"}</button> : <small>陪伴者可以查看材料，只有家庭管理员可以修改清单。</small>}
          </div>
        ) : null}
        <div className="science-card-grid">
          {recommendations.map((item) => (
            <Link className="science-card" href={`/science/${item.experiment.id}`} key={item.experiment.id}>
              <div><span>{DIFFICULTY[item.experiment.difficulty]}</span><span>{item.experiment.estimated_duration_minutes} 分钟</span></div>
              <h3>{item.experiment.title}</h3><p>{item.experiment.guiding_question}</p>
              <strong className={item.ready_at_home ? "ready" : "missing"}>{item.ready_at_home ? "家中材料已齐" : `还缺 ${item.missing_required_materials.join("、")}`}</strong>
              <small>{item.reasons.join(" · ")}</small>
            </Link>
          ))}
        </div>
      </section>

      <section className="science-panel">
        <div className="section-title-row"><div><p className="eyebrow">成长记录</p><h2>实验历史</h2></div><span>{history?.total ?? 0} 次真实探索</span></div>
        <div className="experiment-history">
          {history?.items.map((item) => (
            <Link href={`/science/session/${item.id}`} key={item.id}>
              <strong>{String(item.experiment_snapshot.title ?? "科学实验")}</strong>
              <span>{item.local_date}</span><span>{item.status === "completed" ? "已完成" : item.status === "in_progress" ? "继续实验" : "已放弃"}</span>
            </Link>
          ))}
          {history?.total === 0 ? <p className="empty-storybook">还没有实验记录，从上面的推荐开始吧。</p> : null}
        </div>
      </section>
    </section>
  );
}

export default function SciencePage() { return <ProtectedPage><ScienceHub /></ProtectedPage>; }
