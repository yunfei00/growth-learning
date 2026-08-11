import type { Metadata } from "next";

import { BackendHealth } from "@/components/backend-health";

export const metadata: Metadata = {
  title: "开发状态",
};

const foundations = [
  { label: "Web application", value: "Next.js 16", state: "ready" },
  { label: "API application", value: "FastAPI", state: "ready" },
  { label: "Primary data", value: "PostgreSQL", state: "configured" },
  { label: "Cache foundation", value: "Redis", state: "configured" },
  { label: "Object storage", value: "MinIO", state: "configured" },
];

export default function StatusPage() {
  return (
    <section className="status-page section-shell">
      <div className="status-intro">
        <p className="eyebrow">Development status</p>
        <h1>工程基础状态</h1>
        <p>
          这里展示真实的开发环境连接情况。基础服务标记为“已配置”不代表它们已经在当前设备启动。
        </p>
      </div>

      <BackendHealth />

      <div className="foundation-table" aria-label="基础服务配置状态">
        {foundations.map((item) => (
          <div className="foundation-row" key={item.label}>
            <div>
              <span className="foundation-label">{item.label}</span>
              <strong>{item.value}</strong>
            </div>
            <span className={`tag tag-${item.state}`}>
              {item.state === "ready" ? "已就绪" : "已配置"}
            </span>
          </div>
        ))}
      </div>

      <div className="status-note">
        <p className="eyebrow">Scope note</p>
        <p>
          Phase 1 不包含业务账户、学习数据或模拟仪表盘。页面会随着后续真实产品切片逐步扩展。
        </p>
      </div>
    </section>
  );
}

