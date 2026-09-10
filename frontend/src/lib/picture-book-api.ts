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

export type FamilyPictureBookUpload = {
  title: string;
  pageTexts: string[];
  images: File[];
  cover?: File | null;
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

export async function uploadFamilyPictureBook(
  childId: string,
  payload: FamilyPictureBookUpload,
): Promise<PictureBookImportResult> {
  const form = new FormData();
  form.append("title", payload.title);
  form.append("page_texts", JSON.stringify(payload.pageTexts));
  payload.images.forEach((image) => form.append("images", image, image.name));
  if (payload.cover) form.append("cover", payload.cover, payload.cover.name);

  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/picture-books/manual`,
    { method: "POST", credentials: "include", cache: "no-store", body: form },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as PictureBookImportResult;
}

export async function updateFamilyPictureBook(
  childId: string,
  versionId: string,
  payload: { title: string; pageTexts: string[] },
): Promise<PictureBookDetail> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture-book/manual`,
    {
      method: "PUT",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ title: payload.title, page_texts: payload.pageTexts }),
    },
  );
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as PictureBookDetail;
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

export function pictureBookCoverUrl(childId: string, versionId: string) {
  return `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture/cover`;
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
    `${getApiBaseUrl()}/api/v1/children/${childId}/story-versions/${versionId}/picture/audio/pages/${pageIndex}?refresh=${Date.now()}`,
    {
      credentials: "include",
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
    },
  );
  if (!response.ok) throw await errorFrom(response);
  return await response.blob();
}
