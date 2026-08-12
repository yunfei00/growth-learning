"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiClientError, getAdminOverview, type AdminOverview } from "@/lib/api/client";

const metrics: Array<{ key: keyof AdminOverview; label: string; note: string }> = [
  { key: "users", label: "系统用户", note: "已注册成人账号" },
  { key: "families", label: "家庭", note: "正式家庭边界" },
  { key: "children", label: "孩子", note: "家庭内孩子档案" },
  { key: "characters", label: "汉字知识点", note: "系统规范知识" },
];

export default function AdminOverviewPage() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAdminOverview()
      .then(setOverview)
      .catch((requestError) =>
        setError(
          requestError instanceof ApiClientError
            ? requestError.message
            : "无法加载管理概览",
        ),
      );
  }, []);

  return (
    <section className="admin-page">
      <header className="admin-page-header">
        <div>
          <p className="eyebrow">概览</p>
          <h2>系统运行数据</h2>
          <p>以下数字全部来自当前数据库。</p>
        </div>
        <Link className="button button-primary" href="/admin/characters">
          管理汉字知识库
        </Link>
      </header>

      {error ? (
        <p className="form-message form-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="metric-grid" aria-busy={!overview && !error}>
        {metrics.map((metric) => (
          <article className="metric-card" key={metric.key}>
            <span>{metric.label}</span>
            <strong>{overview ? overview[metric.key] : "—"}</strong>
            <p>{metric.note}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
