import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/app-header";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Growth Learning",
    template: "%s · Growth Learning",
  },
  description: "面向儿童长期学习与成长记录的家庭中心平台。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="site-frame">
          <AppHeader />
          <main>{children}</main>
          <footer className="site-footer">
            <span>Growth Learning</span>
            <span>为长期成长保留真实证据</span>
          </footer>
        </div>
      </body>
    </html>
  );
}

