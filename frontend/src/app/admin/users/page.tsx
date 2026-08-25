"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  ApiClientError,
  type AdminUser,
  type AdminUserPage,
  listAdminUsers,
  updateAdminUserStatus,
} from "@/lib/api/client";

const STATUS_LABELS = {
  active: "正常",
  suspended: "已暂停",
  disabled: "已禁用",
} as const;

const SOURCE_LABELS = {
  legacy: "历史账号",
  platform_invitation: "平台邀请",
  admin_created: "管理员创建",
} as const;

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "从未登录";
}

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [result, setResult] = useState<AdminUserPage | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [accountStatus, setAccountStatus] = useState("");
  const [page, setPage] = useState(1);
  const [workingId, setWorkingId] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setResult(
        await listAdminUsers({ search, accountStatus, page, pageSize: 20 }),
      );
      setError("");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "无法加载用户列表",
      );
    }
  }, [accountStatus, page, search]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const updateStatus = async (
    target: AdminUser,
    nextStatus: AdminUser["account_status"],
  ) => {
    setWorkingId(target.id);
    setError("");
    try {
      await updateAdminUserStatus(target.id, nextStatus);
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "账号状态没有更新成功",
      );
    } finally {
      setWorkingId("");
    }
  };

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="eyebrow">Platform accounts</p>
          <h2>用户管理</h2>
          <p>只展示平台账号元数据和家庭数量，不读取家庭私有内容。</p>
        </div>
      </header>

      <form className="admin-filter-bar" onSubmit={submitSearch}>
        <label>
          <span>搜索姓名或邮箱</span>
          <input
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="姓名或 email@example.com"
            value={searchInput}
          />
        </label>
        <label>
          <span>账号状态</span>
          <select
            onChange={(event) => {
              setAccountStatus(event.target.value);
              setPage(1);
            }}
            value={accountStatus}
          >
            <option value="">全部状态</option>
            <option value="active">正常</option>
            <option value="suspended">已暂停</option>
            <option value="disabled">已禁用</option>
          </select>
        </label>
        <button className="button button-secondary" type="submit">
          搜索
        </button>
      </form>

      {error ? <p className="form-message form-error" role="alert">{error}</p> : null}

      <div className="admin-table-wrap" aria-busy={!result}>
        <table className="admin-data-table">
          <thead>
            <tr>
              <th>用户</th><th>状态</th><th>角色</th><th>注册来源</th>
              <th>注册时间</th><th>最后登录</th><th>家庭</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {result?.items.map((item) => (
              <tr key={item.id}>
                <td><strong>{item.display_name}</strong><small>{item.email}</small></td>
                <td><span className={`status-pill ${item.account_status}`}>{STATUS_LABELS[item.account_status]}</span></td>
                <td>{item.system_role === "admin" ? "系统管理员" : "用户"}</td>
                <td>{SOURCE_LABELS[item.registration_source]}</td>
                <td>{formatDate(item.created_at)}</td>
                <td>{formatDate(item.last_login_at)}</td>
                <td>{item.family_count}</td>
                <td>
                  <div className="admin-row-actions">
                    {item.account_status === "active" ? (
                      <button
                        className="button button-quiet"
                        disabled={workingId === item.id || item.id === currentUser?.id}
                        onClick={() => void updateStatus(item, "suspended")}
                        type="button"
                      >暂停</button>
                    ) : (
                      <button
                        className="button button-secondary"
                        disabled={workingId === item.id}
                        onClick={() => void updateStatus(item, "active")}
                        type="button"
                      >恢复</button>
                    )}
                    {item.account_status !== "disabled" && item.id !== currentUser?.id ? (
                      <button
                        className="button button-quiet danger"
                        disabled={workingId === item.id}
                        onClick={() => void updateStatus(item, "disabled")}
                        type="button"
                      >禁用</button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {result && result.items.length === 0 ? <p className="empty-note">没有符合条件的用户。</p> : null}
      </div>

      {result && result.pages > 1 ? (
        <nav aria-label="用户列表分页" className="pagination-bar">
          <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">上一页</button>
          <span>第 {page} / {result.pages} 页 · 共 {result.total} 人</span>
          <button disabled={page >= result.pages} onClick={() => setPage((value) => value + 1)} type="button">下一页</button>
        </nav>
      ) : null}
    </section>
  );
}
