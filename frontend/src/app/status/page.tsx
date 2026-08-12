import type { Metadata } from "next";

import { BackendHealth } from "@/components/backend-health";

export const metadata: Metadata = {
  title: "服务状态",
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
        <p className="eyebrow">Service status</p>
        <h1>系统服务状态</h1>
        <p>这里展示当前 API 的真实连通状态与已经配置的基础服务。</p>
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
    </section>
  );
}
