"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth-provider";
import {
  ApiClientError,
  type Child,
  type Family,
  listChildren,
  listFamilies,
} from "@/lib/api/client";

const ACTIVE_CHILD_KEY = "growth-learning:active-child-id";

type HouseholdStatus = "idle" | "loading" | "ready" | "error";

type ActiveChildContextValue = {
  status: HouseholdStatus;
  family: Family | null;
  children: Child[];
  activeChild: Child | null;
  error: string;
  setActiveChildId: (childId: string) => void;
  refresh: () => Promise<void>;
};

const ActiveChildContext = createContext<ActiveChildContextValue | null>(null);

export function ActiveChildProvider({ children: content }: { children: ReactNode }) {
  const { status: authStatus } = useAuth();
  const [status, setStatus] = useState<HouseholdStatus>("idle");
  const [family, setFamily] = useState<Family | null>(null);
  const [children, setChildren] = useState<Child[]>([]);
  const [activeChildId, setActiveChildIdState] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (authStatus !== "authenticated") return;
    setStatus("loading");
    setError("");
    try {
      const families = await listFamilies();
      if (families.length === 0) {
        setFamily(null);
        setChildren([]);
        setActiveChildIdState("");
        setStatus("ready");
        return;
      }
      const currentFamily = families[0];
      const householdChildren = await listChildren(currentFamily.id);
      const saved = window.localStorage.getItem(ACTIVE_CHILD_KEY);
      const selected = householdChildren.some((child) => child.id === saved)
        ? saved!
        : (householdChildren[0]?.id ?? "");
      if (selected) window.localStorage.setItem(ACTIVE_CHILD_KEY, selected);
      setFamily(currentFamily);
      setChildren(householdChildren);
      setActiveChildIdState(selected);
      setStatus("ready");
    } catch (requestError) {
      setError(
        requestError instanceof ApiClientError
          ? requestError.message
          : "暂时无法加载家庭和孩子信息",
      );
      setStatus("error");
    }
  }, [authStatus]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (authStatus === "authenticated") {
        void refresh();
      } else if (authStatus === "unauthenticated") {
        setStatus("idle");
        setFamily(null);
        setChildren([]);
        setActiveChildIdState("");
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [authStatus, refresh]);

  useEffect(() => {
    const handleHouseholdChanged = () => void refresh();
    window.addEventListener("growth-learning:household-changed", handleHouseholdChanged);
    return () =>
      window.removeEventListener("growth-learning:household-changed", handleHouseholdChanged);
  }, [refresh]);

  const setActiveChildId = useCallback(
    (childId: string) => {
      if (!children.some((child) => child.id === childId)) return;
      window.localStorage.setItem(ACTIVE_CHILD_KEY, childId);
      setActiveChildIdState(childId);
    },
    [children],
  );
  const activeChild = useMemo(
    () => children.find((child) => child.id === activeChildId) ?? null,
    [activeChildId, children],
  );
  const value = useMemo(
    () => ({ status, family, children, activeChild, error, setActiveChildId, refresh }),
    [status, family, children, activeChild, error, setActiveChildId, refresh],
  );

  return <ActiveChildContext.Provider value={value}>{content}</ActiveChildContext.Provider>;
}

export function useActiveChild(): ActiveChildContextValue {
  const context = useContext(ActiveChildContext);
  if (!context) throw new Error("useActiveChild must be used within ActiveChildProvider");
  return context;
}
