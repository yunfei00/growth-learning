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
import {
  ACTIVE_FAMILY_KEY,
  activeChildKey,
  loadFamilyChildren,
  selectRemembered,
} from "@/lib/household-selection";

const LEGACY_ACTIVE_CHILD_KEY = "growth-learning:active-child-id";

type HouseholdStatus = "idle" | "loading" | "ready" | "error";

type ActiveChildContextValue = {
  status: HouseholdStatus;
  families: Family[];
  activeFamily: Family | null;
  family: Family | null;
  children: Child[];
  activeChild: Child | null;
  error: string;
  setActiveFamilyId: (familyId: string) => void;
  setActiveChildId: (childId: string) => void;
  refresh: () => Promise<void>;
};

const ActiveChildContext = createContext<ActiveChildContextValue | null>(null);

export function ActiveChildProvider({ children: content }: { children: ReactNode }) {
  const { status: authStatus } = useAuth();
  const [status, setStatus] = useState<HouseholdStatus>("idle");
  const [families, setFamilies] = useState<Family[]>([]);
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
      setFamilies(families);
      if (families.length === 0) {
        setFamily(null);
        setChildren([]);
        setActiveChildIdState("");
        setStatus("ready");
        return;
      }
      const currentFamily = selectRemembered(
        families,
        window.localStorage.getItem(ACTIVE_FAMILY_KEY),
      );
      if (!currentFamily) throw new Error("No selectable family");
      window.localStorage.setItem(ACTIVE_FAMILY_KEY, currentFamily.id);
      const familyChildKey = activeChildKey(currentFamily.id);
      const saved =
        window.localStorage.getItem(familyChildKey) ??
        window.localStorage.getItem(LEGACY_ACTIVE_CHILD_KEY);
      const loaded = await loadFamilyChildren(currentFamily.id, saved, listChildren);
      const householdChildren = loaded.children;
      const selected = loaded.activeChild?.id ?? "";
      if (selected) window.localStorage.setItem(familyChildKey, selected);
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
        setFamilies([]);
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

  const setActiveFamilyId = useCallback(
    (familyId: string) => {
      const selectedFamily = families.find((item) => item.id === familyId);
      if (!selectedFamily || selectedFamily.id === family?.id) return;
      window.localStorage.setItem(ACTIVE_FAMILY_KEY, selectedFamily.id);
      setStatus("loading");
      setError("");
      void loadFamilyChildren(
        selectedFamily.id,
        window.localStorage.getItem(activeChildKey(selectedFamily.id)),
        listChildren,
      )
        .then(({ children: householdChildren, activeChild: selected }) => {
          if (selected) {
            window.localStorage.setItem(activeChildKey(selectedFamily.id), selected.id);
          }
          setFamily(selectedFamily);
          setChildren(householdChildren);
          setActiveChildIdState(selected?.id ?? "");
          setStatus("ready");
        })
        .catch((requestError: unknown) => {
          setError(
            requestError instanceof ApiClientError
              ? requestError.message
              : "暂时无法切换家庭",
          );
          setStatus("error");
        });
    },
    [families, family?.id],
  );

  const setActiveChildId = useCallback(
    (childId: string) => {
      if (!children.some((child) => child.id === childId)) return;
      if (!family) return;
      window.localStorage.setItem(activeChildKey(family.id), childId);
      setActiveChildIdState(childId);
    },
    [children, family],
  );
  const activeChild = useMemo(
    () => children.find((child) => child.id === activeChildId) ?? null,
    [activeChildId, children],
  );
  const value = useMemo(
    () => ({
      status,
      families,
      activeFamily: family,
      family,
      children,
      activeChild,
      error,
      setActiveFamilyId,
      setActiveChildId,
      refresh,
    }),
    [
      status,
      families,
      family,
      children,
      activeChild,
      error,
      setActiveFamilyId,
      setActiveChildId,
      refresh,
    ],
  );

  return <ActiveChildContext.Provider value={value}>{content}</ActiveChildContext.Provider>;
}

export function useActiveChild(): ActiveChildContextValue {
  const context = useContext(ActiveChildContext);
  if (!context) throw new Error("useActiveChild must be used within ActiveChildProvider");
  return context;
}
