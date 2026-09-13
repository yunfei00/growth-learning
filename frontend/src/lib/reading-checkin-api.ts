import { getApiBaseUrl, type ReadingSession } from "@/lib/api/client";

type ApiErrorPayload = { detail?: string };

export type ReadingHelpEvent = {
  id: string;
  reading_session_id: string;
  character: string;
  pinyin: string | null;
  help_kind: "character_tap";
  occurred_at: string;
};

export type ReadingCheckinDay = {
  date: string;
  completed: boolean;
  title: string | null;
  story_version_id: string | null;
  reading_session_id: string | null;
  reading_mode: "independent" | "with_help" | null;
  duration_seconds: number | null;
  help_count: number;
  help_characters: string[];
};

export type ReadingCheckinSummary = {
  from_date: string;
  to_date: string;
  today_completed: boolean;
  current_streak: number;
  longest_streak: number;
  completed_days: number;
  total_duration_seconds: number;
  total_help_count: number;
  days: ReadingCheckinDay[];
};

async function errorFrom(response: Response): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null;
  return new Error(payload?.detail || `请求失败（HTTP ${response.status}）`);
}

export async function recordReadingHelp(
  childId: string,
  readingSessionId: string,
  character: string,
): Promise<ReadingHelpEvent> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/reading-sessions/${readingSessionId}/help-events`,
    {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ character }),
    },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as ReadingHelpEvent;
}

export async function completeIndependentDailyReading(
  childId: string,
  readingSessionId: string,
  payload: { duration_seconds?: number; parent_note?: string },
): Promise<ReadingSession> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/reading-sessions/${readingSessionId}/daily-complete`,
    {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as ReadingSession;
}

function localDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export async function getReadingCheckins(
  childId: string,
  options?: { from?: string; to?: string; today?: string },
): Promise<ReadingCheckinSummary> {
  const today = options?.today ?? localDate(new Date());
  const to = options?.to ?? today;
  const fallbackFrom = new Date(`${to}T12:00:00`);
  fallbackFrom.setDate(fallbackFrom.getDate() - 30);
  const from = options?.from ?? localDate(fallbackFrom);
  const query = new URLSearchParams({ from, to, today });
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/reading-checkins?${query.toString()}`,
    { credentials: "include", cache: "no-store", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as ReadingCheckinSummary;
}
