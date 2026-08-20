"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiClientError, getHealth } from "@/lib/api/client";

type HealthState =
  | { kind: "loading"; message: string }
  | { kind: "online"; message: string }
  | { kind: "offline"; message: string };

export function BackendHealth() {
  const [health, setHealth] = useState<HealthState>({
    kind: "loading",
    message: "正在连接后端…",
  });

  const checkHealth = useCallback(async () => {
    try {
      const response = await getHealth();
      setHealth({
        kind: response.status === "ok" ? "online" : "offline",
        message:
          response.status === "ok"
            ? `后端服务正常 · v${response.version} · ${response.revision}`
            : "后端返回未知状态",
      });
    } catch (error) {
      setHealth({
        kind: "offline",
        message:
          error instanceof ApiClientError && error.status
            ? `后端返回 HTTP ${error.status}`
            : "暂时无法连接后端",
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((response) => {
        if (!cancelled) {
          setHealth({
            kind: response.status === "ok" ? "online" : "offline",
            message:
              response.status === "ok"
                ? `后端服务正常 · v${response.version} · ${response.revision}`
                : "后端返回未知状态",
          });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setHealth({
            kind: "offline",
            message:
              error instanceof ApiClientError && error.status
                ? `后端返回 HTTP ${error.status}`
                : "暂时无法连接后端",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const retryHealthCheck = () => {
    setHealth({ kind: "loading", message: "正在连接后端…" });
    void checkHealth();
  };

  return (
    <section className={`health-card health-${health.kind}`} aria-live="polite">
      <div className="health-content">
        <span className="health-indicator" aria-hidden="true" />
        <div>
          <span className="foundation-label">Backend health</span>
          <strong>{health.message}</strong>
          <code>GET /health</code>
        </div>
      </div>
      <button disabled={health.kind === "loading"} onClick={retryHealthCheck} type="button">
        {health.kind === "loading" ? "检查中" : "重新检查"}
      </button>
    </section>
  );
}
