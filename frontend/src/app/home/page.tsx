"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type Child,
  type Family,
  listChildren,
  listFamilies,
} from "@/lib/api/client";

const ACTIVE_CHILD_KEY = "growth-learning:active-child-id";

function formatAge(birthDate: string): string {
  const birth = new Date(`${birthDate}T00:00:00`);
  const today = new Date();
  let months =
    (today.getFullYear() - birth.getFullYear()) * 12 +
    today.getMonth() -
    birth.getMonth();
  if (today.getDate() < birth.getDate()) {
    months -= 1;
  }
  months = Math.max(0, months);
  const years = Math.floor(months / 12);
  const remainingMonths = months % 12;
  if (years === 0) {
    return `${remainingMonths}个月`;
  }
  return remainingMonths === 0 ? `${years}岁` : `${years}岁${remainingMonths}个月`;
}

function ParentHomeContent() {
  const router = useRouter();
  const [family, setFamily] = useState<Family | null>(null);
  const [children, setChildren] = useState<Child[]>([]);
  const [activeChildId, setActiveChildId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadHome = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const families = await listFamilies();
      if (families.length === 0) {
        router.replace("/onboarding");
        return;
      }
      const currentFamily = families[0];
      const familyChildren = await listChildren(currentFamily.id);
      if (familyChildren.length === 0) {
        router.replace("/onboarding");
        return;
      }

      const savedChildId = window.localStorage.getItem(ACTIVE_CHILD_KEY);
      const selected = familyChildren.some((child) => child.id === savedChildId)
        ? savedChildId!
        : familyChildren[0].id;
      window.localStorage.setItem(ACTIVE_CHILD_KEY, selected);
      setFamily(currentFamily);
      setChildren(familyChildren);
      setActiveChildId(selected);
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "暂时无法加载家庭信息",
      );
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    listFamilies()
      .then(async (families) => {
        if (families.length === 0) {
          router.replace("/onboarding");
          return null;
        }
        const currentFamily = families[0];
        const familyChildren = await listChildren(currentFamily.id);
        return { currentFamily, familyChildren };
      })
      .then((result) => {
        if (cancelled || result === null) {
          return;
        }
        if (result.familyChildren.length === 0) {
          router.replace("/onboarding");
          return;
        }
        const savedChildId = window.localStorage.getItem(ACTIVE_CHILD_KEY);
        const selected = result.familyChildren.some((child) => child.id === savedChildId)
          ? savedChildId!
          : result.familyChildren[0].id;
        window.localStorage.setItem(ACTIVE_CHILD_KEY, selected);
        setFamily(result.currentFamily);
        setChildren(result.familyChildren);
        setActiveChildId(selected);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setError(
            requestError instanceof ApiClientError
              ? requestError.message
              : "暂时无法加载家庭信息",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const activeChild = useMemo(
    () => children.find((child) => child.id === activeChildId) ?? null,
    [activeChildId, children],
  );

  const switchChild = (childId: string) => {
    window.localStorage.setItem(ACTIVE_CHILD_KEY, childId);
    setActiveChildId(childId);
  };

  if (isLoading) {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在加载家庭和孩子信息…</p>
      </section>
    );
  }

  if (error || !family || !activeChild) {
    return (
      <section className="center-state section-shell">
        <h1>暂时无法进入家长首页</h1>
        <p>{error || "没有找到可用的家庭资料"}</p>
        <button className="button button-primary" onClick={() => void loadHome()} type="button">
          重新加载
        </button>
      </section>
    );
  }

  const childName = activeChild.nickname || activeChild.display_name;

  return (
    <section className="dashboard-page section-shell">
      <div className="dashboard-toolbar">
        <div>
          <p className="eyebrow">家长首页</p>
          <h1>家庭：{family.name}</h1>
          <p className="role-note">
            当前权限：{family.current_role === "admin" ? "家庭管理员" : "陪伴者"}
          </p>
        </div>
        <ChildSwitcher
          activeChildId={activeChild.id}
          childOptions={children}
          onChange={switchChild}
        />
      </div>

      <div className="welcome-card">
        <div>
          <p className="eyebrow">成长档案</p>
          <h2>你好，{childName} 👋</h2>
          <p>{formatAge(activeChild.birth_date)}</p>
        </div>
        <div className="profile-mark" aria-hidden="true">
          {childName.slice(0, 1)}
        </div>
      </div>

      <section className="today-section">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">Today</p>
            <h2>今日学习</h2>
          </div>
          <span>真实进度将在开始学习后记录</span>
        </div>
        <div className="learning-grid">
          {[
            ["识字学习", "字"],
            ["阅读", "书"],
            ["科学实验", "光"],
          ].map(([title, mark]) => (
            <article className="learning-card" key={title}>
              <span className="learning-mark">{mark}</span>
              <div>
                <h3>{title}</h3>
                <p>尚未开始</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <p className="archive-note">成长学习正在为孩子建立长期学习档案</p>
    </section>
  );
}

export default function ParentHomePage() {
  return (
    <ProtectedPage>
      <ParentHomeContent />
    </ProtectedPage>
  );
}
