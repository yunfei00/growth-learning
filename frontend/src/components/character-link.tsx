"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect } from "react";

const SCROLL_KEY = "growth-learning:character-return-scroll";

export function CharacterLink({
  knowledgePointId,
  children,
  className,
}: {
  knowledgePointId: string;
  children: ReactNode;
  className?: string;
}) {
  const pathname = usePathname();

  useEffect(() => {
    const stored = window.sessionStorage.getItem(SCROLL_KEY);
    if (!stored) return;
    try {
      const marker = JSON.parse(stored) as { pathname: string; scrollY: number };
      if (marker.pathname === pathname) {
        window.sessionStorage.removeItem(SCROLL_KEY);
        window.requestAnimationFrame(() => window.scrollTo({ top: marker.scrollY }));
      }
    } catch {
      window.sessionStorage.removeItem(SCROLL_KEY);
    }
  }, [pathname]);

  return (
    <Link
      className={className}
      href={`/learn/characters/${knowledgePointId}`}
      onClick={() => {
        window.sessionStorage.setItem(
          SCROLL_KEY,
          JSON.stringify({ pathname, scrollY: window.scrollY }),
        );
      }}
    >
      {children}
    </Link>
  );
}
