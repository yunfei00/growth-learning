"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useActiveChild } from "@/components/active-child-provider";
import { ChildSwitcher } from "@/components/child-switcher";
import { ProtectedPage } from "@/components/protected-page";
import {
  ApiClientError,
  type CharacterMasterySummary,
  getCharacterMasterySummary,
} from "@/lib/api/client";

function formatAge(birthDate: string): string {
  const birth = new Date(`${birthDate}T00:00:00`);
  const today = new Date();
  let months =
    (today.getFullYear() - birth.getFullYear()) * 12 + today.getMonth() - birth.getMonth();
  if (today.getDate() < birth.getDate()) months -= 1;
  months = Math.max(0, months);
  const years = Math.floor(months / 12);
  const remainingMonths = months % 12;
  if (years === 0) return `${remainingMonths}个月`;
  return remainingMonths === 0 ? `${years}岁` : `${years}岁${remainingMonths}个月`;
}

function ParentHomeContent() {
  const router = useRouter();
  const {
    status,
    family,
    children,
    activeChild,
    error: householdError,
    setActiveChildId,
    refresh,
  } = useActiveChild();
  const [summary, setSummary] = useState<CharacterMasterySummary | null>(null);
  const [summaryError, setSummaryError] = useState("");

  useEffect(() => {
    if (status === "ready" && (!family || !activeChild)) router.replace("/onboarding");
  }, [activeChild, family, router, status]);

  useEffect(() => {
    if (!activeChild) return;
    let cancelled = false;
    getCharacterMasterySummary(activeChild.id)
      .then((value) => {
        if (!cancelled) {
          setSummary(value);
          setSummaryError("");
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          setSummaryError(
            requestError instanceof ApiClientError
              ? requestError.message
              : "暂时无法加载识字进度",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeChild]);

  if (status === "idle" || status === "loading") {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在加载家庭和孩子信息…</p>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="center-state section-shell">
        <h1>暂时无法进入家长首页</h1>
        <p>{householdError}</p>
        <button className="button button-primary" onClick={() => void refresh()} type="button">
          重新加载
        </button>
      </section>
    );
  }

  if (!family || !activeChild) {
    return (
      <section className="center-state section-shell">
        <span className="loading-spinner" aria-hidden="true" />
        <p>正在前往家庭设置…</p>
      </section>
    );
  }

  const childName = activeChild.nickname || activeChild.display_name;
  const learned = summary
    ? summary.introduced + summary.recognizing + summary.proficient + summary.stable
    : null;
  const switchChild = (childId: string) => {
    setSummary(null);
    setSummaryError("");
    setActiveChildId(childId);
  };

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
          <span>所有数字均来自孩子的真实学习记录</span>
        </div>
        <div className="learning-grid">
          <article className="learning-card learning-card-active">
            <span className="learning-mark">字</span>
            <div>
              <h3>识字学习</h3>
              {summaryError ? (
                <p>{summaryError}</p>
              ) : summary ? (
                <p>
                  已接触 {learned} 字 · 稳定掌握 {summary.stable} 字
                </p>
              ) : (
                <p>正在读取真实进度…</p>
              )}
              <Link className="card-link" href="/learn/characters">
                开始学习
              </Link>
            </div>
          </article>
          {[
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

      <p className="archive-note">成长学习正在为孩子建立长期、可追溯的学习档案</p>
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
