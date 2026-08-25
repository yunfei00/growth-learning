"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import {
  ApiClientError,
  type CreatedPlatformInvitation,
  type PlatformInvitationPage,
  createPlatformInvitation,
  listPlatformInvitations,
  revokePlatformInvitation,
} from "@/lib/api/client";

const STATUS_LABELS: Record<string, string> = {
  active: "可使用", used: "已使用", exhausted: "已用完", expired: "已过期", revoked: "已撤销",
};

function defaultExpiry(): string {
  const value = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 16);
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
}

export default function AdminInvitationsPage() {
  const [result, setResult] = useState<PlatformInvitationPage | null>(null);
  const [created, setCreated] = useState<CreatedPlatformInvitation | null>(null);
  const [expiresAt, setExpiresAt] = useState(defaultExpiry);
  const [maxUses, setMaxUses] = useState("1");
  const [email, setEmail] = useState("");
  const [page, setPage] = useState(1);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setResult(await listPlatformInvitations(page, 20));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "无法加载邀请码");
    }
  }, [page]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setWorking(true); setError(""); setMessage(""); setCreated(null);
    try {
      const invitation = await createPlatformInvitation({
        expires_at: new Date(expiresAt).toISOString(),
        max_uses: Number(maxUses),
        email_constraint: email.trim() || null,
      });
      setCreated(invitation);
      setMessage("邀请码已生成。完整邀请码仅显示这一次，请立即复制并安全发送。");
      setPage(1);
      await load();
    } catch (requestError) {
      setError(requestError instanceof ApiClientError ? requestError.message : "邀请码生成失败");
    } finally { setWorking(false); }
  };

  const copyCode = async () => {
    if (!created) return;
    await navigator.clipboard.writeText(created.invitation_code);
    setMessage("邀请码已复制。完整邀请码关闭本提示后无法再次查看。");
  };

  const revoke = async (id: string) => {
    setWorking(true); setError("");
    try { await revokePlatformInvitation(id); await load(); }
    catch (requestError) { setError(requestError instanceof ApiClientError ? requestError.message : "撤销失败"); }
    finally { setWorking(false); }
  };

  return (
    <section className="admin-page">
      <header className="admin-page-header"><div><p className="eyebrow">Platform invitations</p><h2>邀请码管理</h2><p>完整邀请码只在创建响应中出现一次，数据库和列表均不保存明文。</p></div></header>

      <form className="invitation-create-panel" onSubmit={(event) => void submit(event)}>
        <label><span>用途</span><input disabled value="创建平台账号" /></label>
        <label><span>过期时间</span><input min={new Date().toISOString().slice(0, 16)} onChange={(event) => setExpiresAt(event.target.value)} required type="datetime-local" value={expiresAt} /></label>
        <label><span>最大使用次数</span><input max="100" min="1" onChange={(event) => setMaxUses(event.target.value)} required type="number" value={maxUses} /></label>
        <label><span>绑定邮箱（可选）</span><input onChange={(event) => setEmail(event.target.value)} placeholder="mom@example.com" type="email" value={email} /></label>
        <button className="button button-primary" disabled={working} type="submit">{working ? "生成中…" : "生成邀请码"}</button>
      </form>

      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}
      {created ? (
        <section className="one-time-secret" aria-label="一次性显示的邀请码">
          <div><small>仅本次显示</small><strong>{created.invitation_code}</strong></div>
          <button className="button button-secondary" onClick={() => void copyCode()} type="button">复制邀请码</button>
          <button className="button button-quiet" onClick={() => setCreated(null)} type="button">我已保存，关闭</button>
        </section>
      ) : null}

      <div className="admin-table-wrap" aria-busy={!result}>
        <table className="admin-data-table">
          <thead><tr><th>邀请码</th><th>状态</th><th>创建时间</th><th>过期时间</th><th>使用次数</th><th>邮箱限制</th><th>创建人</th><th>最后使用</th><th>操作</th></tr></thead>
          <tbody>{result?.items.map((item) => (
            <tr key={item.id}>
              <td><strong>{item.code_hint}</strong></td>
              <td><span className={`status-pill ${item.status}`}>{STATUS_LABELS[item.status]}</span></td>
              <td>{formatDate(item.created_at)}</td><td>{formatDate(item.expires_at)}</td>
              <td>{item.used_count} / {item.max_uses}</td><td>{item.email_constraint || "不限邮箱"}</td>
              <td>{item.created_by_display_name}</td><td>{formatDate(item.last_used_at)}</td>
              <td>{item.status === "active" ? <button className="button button-quiet danger" disabled={working} onClick={() => void revoke(item.id)} type="button">撤销</button> : "—"}</td>
            </tr>
          ))}</tbody>
        </table>
        {result && result.items.length === 0 ? <p className="empty-note">还没有平台邀请码。</p> : null}
      </div>
      {result && result.pages > 1 ? <nav aria-label="邀请码分页" className="pagination-bar"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">上一页</button><span>第 {page} / {result.pages} 页</span><button disabled={page >= result.pages} onClick={() => setPage((value) => value + 1)} type="button">下一页</button></nav> : null}
    </section>
  );
}
