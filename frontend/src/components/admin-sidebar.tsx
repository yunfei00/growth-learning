"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_GROUPS = [
  {
    label: null,
    items: [["/admin", "概览"]],
  },
  {
    label: "平台账号",
    items: [
      ["/admin/users", "用户"],
      ["/admin/invitations", "邀请码"],
    ],
  },
  {
    label: "内容管理",
    items: [
      ["/admin/knowledge", "知识点"],
      ["/admin/characters", "汉字"],
      ["/admin/pinyin", "拼音"],
      ["/admin/math", "数学"],
      ["/admin/english", "英语"],
      ["/admin/science", "科学实验"],
      ["/admin/courses", "课程与 Catalog"],
    ],
  },
] as const;

function routeIsActive(pathname: string, href: string): boolean {
  return href === "/admin" ? pathname === href : pathname.startsWith(href);
}

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="admin-sidebar">
      <div className="admin-sidebar-title">
        <p className="eyebrow">成长学习</p>
        <h1>管理后台</h1>
      </div>
      <nav aria-label="管理后台导航">
        {NAV_GROUPS.map((group, index) => (
          <div className="admin-nav-group" key={group.label ?? `primary-${index}`}>
            {group.label ? <p>{group.label}</p> : null}
            {group.items.map(([href, label]) => {
              const active = routeIsActive(pathname, href);
              return (
                <Link aria-current={active ? "page" : undefined} href={href} key={href}>
                  {label}
                </Link>
              );
            })}
          </div>
        ))}
        <div className="admin-nav-group">
          <p>系统</p>
          <span aria-disabled="true">系统配置（暂未开放）</span>
        </div>
      </nav>
    </aside>
  );
}
