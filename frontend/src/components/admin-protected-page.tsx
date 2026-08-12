"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { useAuth } from "@/components/auth-provider";

export function AdminProtectedPage({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { status, user } = useAuth();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    } else if (status === "authenticated" && user?.system_role !== "admin") {
      router.replace("/home");
    }
  }, [router, status, user]);

  if (status !== "authenticated" || user?.system_role !== "admin") {
    return (
      <section className="center-state section-shell" aria-live="polite">
        <span className="loading-spinner" aria-hidden="true" />
        <p>
          {status === "loading"
            ? "正在确认系统管理员权限…"
            : status === "unauthenticated"
              ? "正在前往登录页面…"
              : "没有系统管理员权限，正在返回…"}
        </p>
      </section>
    );
  }

  return children;
}
