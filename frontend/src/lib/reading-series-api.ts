import { getApiBaseUrl } from "@/lib/api/client";

export type ReadingSeriesEpisode = {
  episode_number: number;
  chapter_title: string;
  title: string;
  status: "completed" | "in_progress" | "current" | "upcoming";
  story_version_id: string | null;
  paragraphs: string[];
  focus_characters: string[];
};

export type ReadingSeriesProgress = {
  series_id: string;
  slug: string;
  title: string;
  season_number: number;
  total_episodes: number;
  completed_episodes: number;
  progress_percent: number;
  current_episode_number: number | null;
  current_episode_title: string | null;
  current_chapter_title: string | null;
  current_story_version_id: string | null;
  episodes: ReadingSeriesEpisode[];
};

export async function getCurrentReadingSeries(childId: string): Promise<ReadingSeriesProgress> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/reading-series/current`,
    {
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    },
  );
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail || `请求失败（HTTP ${response.status}）`);
  }
  return (await response.json()) as ReadingSeriesProgress;
}
