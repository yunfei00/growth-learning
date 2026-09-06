import { getApiBaseUrl } from "@/lib/api/client";

type ApiErrorPayload = { detail?: string };

export type OpenPictureBook = {
  source_provider: "gdl";
  source_book_id: string;
  title: string;
  description: string;
  reading_level: "1" | "2";
  license_name: string;
  source_url: string;
  thumbnail_url: string | null;
  publisher: string | null;
  authors: string[];
};

export type PictureBookPage = {
  position: number;
  text: string;
  image_available: boolean;
  image_alt: string | null;
  pinyin: Array<string | null>;
};

export type PictureBookDetail = {
  id: string;
  story_version_id: string;
  title: string;
  source_provider: string;
  source_book_id: string;
  source_url: string;
  license_name: string;
  reading_level: string;
  attribution: Record<string, unknown>;
  pages: PictureBookPage[];
};

export type PictureBookImportResult = {
  picture_book_id: string;
  story_version_id: string;
  imported: boolean;
  audio_prepared: boolean;
};

async function errorFrom(response: Response): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null;
  return new Error(payload?.detail || `请求失败（HTTP ${response.status}）`);
}

export async function listOpenPictureBooks(
  childId: string,
  level?: "1" | "2",
): Promise<OpenPictureBook[]> {
  const query = level ? `?level=${level}` : "";
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/open-picture-books${query}`,
    { credentials: "include", cache: "no-store", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as OpenPictureBook[];
}

export async function importOpenPictureBook(
  childId: string,
  sourceBookId: string,
): Promise<PictureBookImportResult> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/open-picture-books/gdl/${sourceBookId}/import`,
    { method: "POST", credentials: "include", cache: "no-store" },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as PictureBookImportResult;
}

export async function getPictureBook(
  childId: string,
  versionId: string,
): Promise<PictureBookDetail> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture-book`,
    { credentials: "include", cache: "no-store", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as PictureBookDetail;
}

export function picturePageImageUrl(childId: string, versionId: string, pageIndex: number) {
  return `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture/pages/${pageIndex}/image`;
}

export async function preparePictureBookAudio(childId: string, versionId: string): Promise<void> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture/audio/prepare`,
    { method: "POST", credentials: "include", cache: "no-store" },
  );
  if (!response.ok) throw await errorFrom(response);
}

export async function fetchPictureBookPageAudio(
  childId: string,
  versionId: string,
  pageIndex: number,
): Promise<Blob> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture/audio/pages/${pageIndex}`,
    { credentials: "include", cache: "force-cache" },
  );
  if (!response.ok) throw await errorFrom(response);
  return await response.blob();
}
