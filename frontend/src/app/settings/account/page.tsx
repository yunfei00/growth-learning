"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProtectedPage } from "@/components/protected-page";
import { useAuth } from "@/components/auth-provider";
import {
  ApiClientError,
  type AccountMetadata,
  changeAccountPassword,
  getAccountMetadata,
  logoutAllDevices,
} from "@/lib/api/client";

function AccountSettingsContent() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [account, setAccount] = useState<AccountMetadata | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getAccountMetadata().then(setAccount).catch((requestError) => setError(requestError instanceof ApiClientError ? requestError.message : "无法加载账号资料"));
  }, []);

  const changePassword = async (event: FormEvent) => {
    event.preventDefault(); setError(""); setMessage("");
    if (newPassword !== confirmPassword) { setError("两次输入的新密码不一致"); return; }
    setWorking(true);
    try {
      await changeAccountPassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      await refresh();
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setMessage("密码已修改，其他设备上的旧会话已经失效。");
    } catch (requestError) { setError(requestError instanceof ApiClientError ? requestError.message : "密码修改失败"); }
    finally { setWorking(false); }
  };

  const logoutAll = async () => {
    setWorking(true); setError("");
    try { await logoutAllDevices(); router.replace("/login"); router.refresh(); }
    catch (requestError) { setError(requestError instanceof ApiClientError ? requestError.message : "退出所有设备失败"); setWorking(false); }
  };

  return (
    <section className="settings-page account-settings-page section-shell">
      <header><p className="eyebrow">Account security</p><h1>账号与安全</h1><p className="role-note">修改密码会使其他设备的旧登录立即失效。</p></header>
      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}
      {message ? <p className="form-message form-success" role="status">{message}</p> : null}
      <section className="account-metadata-card">
        <h2>账号资料</h2>
        <dl><div><dt>姓名</dt><dd>{account?.display_name ?? "—"}</dd></div><div><dt>邮箱</dt><dd>{account?.email ?? "—"}</dd></div><div><dt>创建时间</dt><dd>{account ? new Date(account.created_at).toLocaleString("zh-CN", { hour12: false }) : "—"}</dd></div></dl>
      </section>
      <form className="account-security-card form-stack" onSubmit={(event) => void changePassword(event)}>
        <h2>修改密码</h2>
        <label><span>当前密码</span><input autoComplete="current-password" onChange={(event) => setCurrentPassword(event.target.value)} required type="password" value={currentPassword} /></label>
        <label><span>新密码</span><input autoComplete="new-password" minLength={10} onChange={(event) => setNewPassword(event.target.value)} required type="password" value={newPassword} /></label>
        <label><span>确认新密码</span><input autoComplete="new-password" minLength={10} onChange={(event) => setConfirmPassword(event.target.value)} required type="password" value={confirmPassword} /></label>
        <button className="button button-primary" disabled={working} type="submit">保存新密码</button>
      </form>
      <section className="account-security-card danger-zone"><div><h2>退出所有设备</h2><p>立即作废当前账号的全部登录 Cookie，包括本设备。</p></div><button className="button button-quiet danger" disabled={working} onClick={() => void logoutAll()} type="button">退出所有设备</button></section>
    </section>
  );
}

export default function AccountSettingsPage() {
  return <ProtectedPage><AccountSettingsContent /></ProtectedPage>;
}
