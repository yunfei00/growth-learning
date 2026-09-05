import { getApiBaseUrl, type StoryVersion } from "@/lib/api/client";

type ApiErrorPayload = { detail?: string };

export type ParentStoryCreateResponse = {
  generation_run_id: string;
  status: "succeeded";
  attempt_count: number;
  version: StoryVersion;
};

async function errorFrom(response: Response): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null;
  return new Error(payload?.detail || `请求失败（HTTP ${response.status}）`);
}

export async function createParentStory(
  childId: string,
  payload: { title: string; content: string },
): Promise<ParentStoryCreateResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/children/${childId}/stories/manual`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as ParentStoryCreateResponse;
}

export async function prepareStoryAudio(childId: string, versionId: string): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/audio/prepare`,
    { method: "POST", credentials: "include", cache: "no-store" },
  );
  if (!response.ok) throw await errorFrom(response);
}

export async function fetchStoryParagraphAudio(
  childId: string,
  versionId: string,
  paragraphIndex: number,
): Promise<Blob> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/audio/paragraphs/${paragraphIndex}`,
    { credentials: "include", cache: "force-cache" },
  );
  if (!response.ok) throw await errorFrom(response);
  return await response.blob();
}
