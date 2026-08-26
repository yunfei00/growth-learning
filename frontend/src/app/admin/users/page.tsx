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

function formatDate(value: string | null, fallback = "—"): string {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : fallback;
}

function UserActionSelect({
  item,
  currentUserId,
  working,
  onChange,
}: {
  item: AdminUser;
  currentUserId?: string;
  working: boolean;
  onChange: (target: AdminUser, nextStatus: AdminUser["account_status"]) => void;
}) {
  if (item.id === currentUserId) {
    return <span className="admin-current-account">当前账号</span>;
  }

  return (
    <select
      aria-label={`管理 ${item.display_name} 的账号状态`}
      className="admin-action-select"
      disabled={working}
      onChange={(event) => {
        if (event.target.value) {
          onChange(item, event.target.value as AdminUser["account_status"]);
        }
      }}
      value=""
    >
      <option disabled value="">{working ? "处理中…" : "操作…"}</option>
      {item.account_status !== "active" ? <option value="active">恢复</option> : null}
      {item.account_status === "active" ? <option value="suspended">暂停</option> : null}
      {item.account_status !== "disabled" ? <option value="disabled">禁用</option> : null}
    </select>
  );
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

      <div className="admin-table-wrap admin-users-list" aria-busy={!result}>
        <table className="admin-data-table admin-users-table">
          <thead>
            <tr>
              <th>用户</th><th>状态</th><th>角色 / 来源</th>
              <th>最近登录</th><th>家庭</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {result?.items.map((item) => (
              <tr key={item.id}>
                <td className="admin-primary-cell">
                  <strong>{item.display_name}</strong>
                  <small>{item.email}</small>
                  <small>注册于 {formatDate(item.created_at)}</small>
                </td>
                <td><span className={`status-pill ${item.account_status}`}>{STATUS_LABELS[item.account_status]}</span></td>
                <td>
                  <strong>{item.system_role === "admin" ? "系统管理员" : "用户"}</strong>
                  <small>{SOURCE_LABELS[item.registration_source]}</small>
                </td>
                <td>{formatDate(item.last_login_at, "从未登录")}</td>
                <td>{item.family_count}</td>
                <td>
                  <UserActionSelect
                    currentUserId={currentUser?.id}
                    item={item}
                    onChange={(target, nextStatus) => void updateStatus(target, nextStatus)}
                    working={workingId === item.id}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="admin-mobile-card-list">
          {result?.items.map((item) => (
            <article className="admin-mobile-card" key={item.id}>
              <header>
                <div><strong>{item.display_name}</strong><small>{item.email}</small></div>
                <span className={`status-pill ${item.account_status}`}>{STATUS_LABELS[item.account_status]}</span>
              </header>
              <dl>
                <div><dt>角色</dt><dd>{item.system_role === "admin" ? "系统管理员" : "用户"}</dd></div>
                <div><dt>来源</dt><dd>{SOURCE_LABELS[item.registration_source]}</dd></div>
                <div><dt>注册</dt><dd>{formatDate(item.created_at)}</dd></div>
                <div><dt>最近登录</dt><dd>{formatDate(item.last_login_at, "从未登录")}</dd></div>
                <div><dt>家庭</dt><dd>{item.family_count}</dd></div>
              </dl>
              <footer>
                <UserActionSelect
                  currentUserId={currentUser?.id}
                  item={item}
                  onChange={(target, nextStatus) => void updateStatus(target, nextStatus)}
                  working={workingId === item.id}
                />
              </footer>
            </article>
          ))}
        </div>
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
