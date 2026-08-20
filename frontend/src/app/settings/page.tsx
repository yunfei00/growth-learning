"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type RewardSettings,
  createRewardGoal,
  getRewardSettings,
  updateRewardSettings,
} from "@/lib/api/client";

function FamilySettingsContent() {
  const { status, family } = useActiveChild();
  const [settings, setSettings] = useState<RewardSettings | null>(null);
  const [title, setTitle] = useState("");
  const [stars, setStars] = useState("20");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!family) return;
    try {
      setSettings(await getRewardSettings(family.id));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "暂时无法加载家庭设置");
    }
  }, [family]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  if (status !== "ready" || !family) {
    return <section className="center-state section-shell"><span className="loading-spinner" /><p>正在打开家庭设置…</p></section>;
  }
  const canManage = family.current_role === "admin";

  const toggleStars = async () => {
    if (!settings || !canManage) return;
    setWorking(true); setMessage(""); setError("");
    try {
      setSettings(await updateRewardSettings(family.id, !settings.stars_enabled));
      setMessage("星星鼓励设置已保存。历史记录不会被删除。");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "设置没有保存成功");
    } finally { setWorking(false); }
  };

  const addGoal = async (event: FormEvent) => {
    event.preventDefault();
    if (!canManage || !title.trim()) return;
    const required = Number(stars);
    if (!Number.isInteger(required) || required < 1 || required > 10000) {
      setError("星星数量需要是 1 到 10000 之间的整数。"); return;
    }
    setWorking(true); setMessage(""); setError("");
    try {
      await createRewardGoal(family.id, title.trim(), required);
      setTitle(""); setStars("20"); await load(); setMessage("家庭小目标已添加。");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "小目标没有保存成功");
    } finally { setWorking(false); }
  };

  return (
    <section className="settings-page section-shell">
      <header><p className="eyebrow">Family settings</p><h1>家庭设置</h1><p className="role-note">成长鼓励由家庭选择；它不改变学习证据或知识掌握状态。</p></header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}
      {!settings ? <div className="center-state compact"><span className="loading-spinner" /><p>正在读取设置…</p></div> : (
        <>
          <section className="reward-setting-card"><div><h2>正向星星鼓励</h2><p>只按真实完成与参与增加；不按每一道答题累计，也不会扣除星星。</p></div><button aria-pressed={settings.stars_enabled} className={`setting-toggle ${settings.stars_enabled ? "on" : ""}`} disabled={!canManage || working} onClick={() => void toggleStars()} type="button"><span />{settings.stars_enabled ? "已开启" : "未开启"}</button></section>
          <section className="reward-goals-panel"><div><h2>家庭小目标</h2><p>例如一起去公园、选择周末故事。请避免把成长变成物质竞赛。</p></div>
            <div className="reward-goal-list">{settings.goals.map((goal) => <article key={goal.id}><span>🎁</span><strong>{goal.title}</strong><small>{goal.required_stars} 颗星</small></article>)}{settings.goals.length === 0 ? <p className="empty-note">还没有家庭小目标。</p> : null}</div>
            {canManage ? <form className="reward-goal-form" onSubmit={(event) => void addGoal(event)}><label>目标名称<input maxLength={120} onChange={(event) => setTitle(event.target.value)} placeholder="例如：周末一起去公园" required value={title} /></label><label>需要星星<input inputMode="numeric" min="1" max="10000" onChange={(event) => setStars(event.target.value)} required type="number" value={stars} /></label><button className="button button-primary" disabled={working} type="submit">{working ? "保存中…" : "添加目标"}</button></form> : <p className="role-note">陪伴者可以查看，只有家庭管理员可以修改鼓励设置。</p>}
          </section>
        </>
      )}
    </section>
  );
}

export default function SettingsPage() {
  return <ProtectedPage><FamilySettingsContent /></ProtectedPage>;
}
