"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";

export function AppHeader() {
  const router = useRouter();
  const { status, user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      router.replace("/login");
      router.refresh();
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="成长学习首页">
        <span className="brand-mark" aria-hidden="true">
          长
        </span>
        <span>成长学习</span>
      </Link>
      <nav aria-label="主要导航">
        {status === "authenticated" ? (
          <>
            <Link href="/home">家长首页</Link>
            <Link href="/learn/characters">识字学习</Link>
            {user?.system_role === "admin" ? <Link href="/admin">管理后台</Link> : null}
            <span className="header-user">{user?.display_name}</span>
            <button
              className="nav-button"
              disabled={isLoggingOut}
              onClick={() => void handleLogout()}
              type="button"
            >
              {isLoggingOut ? "退出中…" : "退出"}
            </button>
          </>
        ) : status === "unauthenticated" ? (
          <>
            <Link href="/login">登录</Link>
            <Link className="nav-register" href="/register">
              创建账号
            </Link>
          </>
        ) : (
          <span className="header-user">正在加载…</span>
        )}
      </nav>
    </header>
  );
}
