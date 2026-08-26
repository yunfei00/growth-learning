import type { ReactNode } from "react";

import { AdminProtectedPage } from "@/components/admin-protected-page";
import { AdminSidebar } from "@/components/admin-sidebar";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminProtectedPage>
      <div className="admin-shell section-shell">
        <AdminSidebar />
        <div className="admin-content">{children}</div>
      </div>
    </AdminProtectedPage>
  );
}
