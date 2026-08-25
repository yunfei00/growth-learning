"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { useAuth } from "@/components/auth-provider";

const PARENT_PRIMARY = [
  ["/home", "首页", "⌂"],
  ["/learn/characters", "学习", "字"],
  ["/read", "阅读", "读"],
  ["/science", "科学", "科"],
  ["/growth", "成长", "树"],
] as const;

const CHILD_PRIMARY = [
  ["/kids", "今天", "☀"],
  ["/kids/stories", "故事", "📖"],
  ["/kids/science", "科学", "🔬"],
  ["/kids/growth-tree", "成长树", "🌳"],
  ["/kids/achievements", "成就", "🏅"],
] as const;

const CHILD_MODE_KEY = "growth-learning:experience-mode";

function NavLinks({
  items,
  pathname,
  className,
}: {
  items: readonly (readonly [string, string, string])[];
  pathname: string;
  className: string;
}) {
  return (
    <nav
      aria-label={className.includes("child") ? "孩子模式导航" : "家长模式导航"}
      className={className}
    >
      {items.map(([href, label, icon]) => {
        const childRouteActive =
          (href === "/kids" &&
            (pathname.startsWith("/learn/") || pathname.startsWith("/teacher-tasks/"))) ||
          (href === "/kids/stories" && pathname.startsWith("/read")) ||
          (href === "/kids/science" && pathname.startsWith("/science"));
        const active =
          childRouteActive ||
          (href === "/kids" ? pathname === href : pathname.startsWith(href));
        return (
          <Link aria-current={active ? "page" : undefined} href={href} key={href}>
            <span aria-hidden="true">{icon}</span>
            <small>{label}</small>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { status, user, logout } = useAuth();
  const { activeChild } = useActiveChild();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [childMode, setChildMode] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (pathname.startsWith("/kids")) {
        window.localStorage.setItem(CHILD_MODE_KEY, "child");
        setChildMode(true);
        return;
      }
      setChildMode(window.localStorage.getItem(CHILD_MODE_KEY) === "child");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [pathname]);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      window.localStorage.removeItem(CHILD_MODE_KEY);
      setChildMode(false);
      router.replace("/login");
      router.refresh();
    } finally {
      setIsLoggingOut(false);
    }
  };

  const exitChildMode = () => {
    window.localStorage.removeItem(CHILD_MODE_KEY);
    setChildMode(false);
    router.push("/home");
  };

  if (status === "authenticated" && childMode) {
    return (
      <header className="site-header child-mode-header">
        <Link className="child-mode-brand" href="/kids" aria-label="孩子模式今天">
          <span aria-hidden="true">🌱</span>
          <span>{activeChild?.nickname || activeChild?.display_name || "成长学习"}</span>
        </Link>
        <NavLinks
          className="child-inline-nav child-nav"
          items={CHILD_PRIMARY}
          pathname={pathname}
        />
        <button className="parent-mode-exit" onClick={exitChildMode} type="button">
          <span aria-hidden="true">🔒</span> 家长模式
        </button>
      </header>
    );
  }

  return (
    <>
      <header className="site-header parent-mode-header">
        <Link className="brand" href="/" aria-label="成长学习首页">
          <span className="brand-mark" aria-hidden="true">长</span>
          <span>成长学习</span>
        </Link>
        <nav aria-label="账户和扩展导航" className="parent-account-nav">
          {status === "authenticated" ? (
            <>
              <Link href="/courses">课程</Link>
              <Link href="/teacher-collaboration">老师</Link>
              <Link href="/settings">设置</Link>
              <Link href="/teacher">教师模式</Link>
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
              <Link className="nav-register" href="/register">使用邀请码注册</Link>
            </>
          ) : (
            <span className="header-user">正在加载…</span>
          )}
        </nav>
      </header>
      {status === "authenticated" ? (
        <>
          <NavLinks
            className="desktop-mode-nav parent-nav"
            items={PARENT_PRIMARY}
            pathname={pathname}
          />
          <NavLinks
            className="mobile-bottom-nav parent-nav"
            items={PARENT_PRIMARY}
            pathname={pathname}
          />
        </>
      ) : null}
    </>
  );
}
