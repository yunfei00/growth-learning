import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/app-header";
import { AuthProvider } from "@/components/auth-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "成长学习",
    template: "%s · 成长学习",
  },
  description: "为孩子建立长期、真实、可持续的成长学习档案。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AuthProvider>
          <div className="site-frame">
            <AppHeader />
            <main>{children}</main>
            <footer className="site-footer">
              <span>成长学习</span>
              <span>为孩子的长期成长保留真实记录</span>
            </footer>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
