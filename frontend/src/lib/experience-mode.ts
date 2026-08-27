"use client";

import { useEffect, useState } from "react";

export const CHILD_MODE_KEY = "growth-learning:experience-mode";

export function useChildExperienceMode(): boolean {
  const [childMode, setChildMode] = useState<boolean | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setChildMode(window.localStorage.getItem(CHILD_MODE_KEY) === "child");
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return childMode !== false;
}
