"use client";

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { useAuth } from "@/components/auth-provider";

export function ProtectedPage({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [router, status]);

  if (status !== "authenticated") {
    return (
      <section className="center-state section-shell" aria-live="polite">
        <span className="loading-spinner" aria-hidden="true" />
        <p>{status === "loading" ? "正在确认登录状态…" : "正在前往登录页面…"}</p>
      </section>
    );
  }

  return children;
}
