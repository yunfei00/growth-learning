import Link from "next/link";
import type { ReactNode } from "react";

import { AdminProtectedPage } from "@/components/admin-protected-page";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminProtectedPage>
      <div className="admin-shell section-shell">
        <aside className="admin-sidebar">
          <div>
            <p className="eyebrow">成长学习</p>
            <h1>管理后台</h1>
          </div>
          <nav aria-label="管理后台导航">
            <Link href="/admin">概览</Link>
            <p>知识库</p>
            <Link href="/admin/characters">汉字</Link>
            <Link href="/admin/science">科学实验</Link>
            <p>以后扩展</p>
            <span aria-disabled="true">课程</span>
            <span aria-disabled="true">系统配置</span>
          </nav>
        </aside>
        <div className="admin-content">{children}</div>
      </div>
    </AdminProtectedPage>
  );
}
