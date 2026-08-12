const DEFAULT_API_PORT = "8000";
const REQUEST_TIMEOUT_MS = 8_000;

export type User = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  system_role: "user" | "admin";
  created_at: string;
  updated_at: string;
};

export type AdminOverview = {
  users: number;
  families: number;
  children: number;
  characters: number;
};

export type CharacterStatus = "active" | "archived";

export type ChineseCharacter = {
  id: string;
  character: string;
  pinyin: string;
  stroke_count: number | null;
  radical: string | null;
  frequency_rank: number | null;
  difficulty_level: number | null;
  simple_meaning: string | null;
  example_sentence: string | null;
  common_words: string[];
  tags: string[];
  is_enabled: boolean;
  status: CharacterStatus;
  source_type: string;
  source_reference: string | null;
  created_at: string;
  updated_at: string;
};

export type CharacterPage = {
  items: ChineseCharacter[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type CharacterInput = {
  character: string;
  pinyin: string;
  stroke_count?: number | null;
  radical?: string | null;
  simple_meaning?: string | null;
  example_sentence?: string | null;
  common_words: string[];
  tags: string[];
  is_enabled: boolean;
};

export type ImportReport = {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
};

export type FamilyRole = "admin" | "companion";

export type Family = {
  id: string;
  name: string;
  current_role: FamilyRole;
  created_at: string;
  updated_at: string;
};

export type ChildGender = "male" | "female" | "other";

export type Child = {
  id: string;
  family_id: string;
  display_name: string;
  nickname: string | null;
  birth_date: string;
  gender: ChildGender | null;
  avatar_key: string | null;
  created_at: string;
  updated_at: string;
};

export type HealthResponse = {
  status: "ok";
};

export type MasteryLevel =
  | "unlearned"
  | "introduced"
  | "recognizing"
  | "proficient"
  | "stable";

export type CharacterMasterySummary = {
  total_enabled: number;
  unlearned: number;
  introduced: number;
  recognizing: number;
  proficient: number;
  stable: number;
  priority: number;
  learning_records: number;
  assessment_items: number;
};

export type CharacterMasteryState = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  common_words: string[];
  simple_meaning: string | null;
  mastery_level: MasteryLevel;
  mastery_score: number;
  first_introduced_at: string | null;
  last_learning_at: string | null;
  last_assessed_at: string | null;
  correct_count: number;
  hinted_correct_count: number;
  uncertain_count: number;
  incorrect_count: number;
  consecutive_correct: number;
  consecutive_incorrect: number;
  average_response_time_ms: number | null;
  is_priority: boolean;
  algorithm_version: string;
};

export type CharacterMasteryPage = {
  items: CharacterMasteryState[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type CharacterRecommendation = {
  id: string;
  character: string;
  pinyin: string;
  common_words: string[];
  simple_meaning: string | null;
  example_sentence: string | null;
  mastery_level: MasteryLevel;
  is_priority: boolean;
};

export type TimelineItem = {
  id: string;
  evidence_type: "learning" | "assessment";
  value: string;
  occurred_at: string;
  response_time_ms: number | null;
};

export type CharacterMasteryDetail = {
  state: CharacterMasteryState;
  timeline: TimelineItem[];
};

export type EvidenceSession = {
  id: string;
  child_id: string;
  status: "in_progress" | "completed" | "abandoned";
  source: string;
  item_count: number;
  started_at: string;
  completed_at: string | null;
  created_at: string;
};

type ErrorPayload = {
  detail?: string | Array<{ msg?: string }>;
};

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

function getApiBaseUrl(): string {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/$/, "");
  }

  const apiUrl = new URL(window.location.origin);
  apiUrl.port = process.env.NEXT_PUBLIC_API_PORT?.trim() || DEFAULT_API_PORT;
  return apiUrl.origin;
}

function errorMessage(payload: ErrorPayload | null, fallback: string): string {
  if (typeof payload?.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload?.detail)) {
    const messages = payload.detail.flatMap((item) => (item.msg ? [item.msg] : []));
    if (messages.length > 0) {
      return messages.join("；");
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const hasBody = init?.body !== undefined;

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      cache: init?.cache ?? "no-store",
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as ErrorPayload | null;
      if (response.status === 401) {
        window.dispatchEvent(new Event("growth-learning:unauthorized"));
      }
      throw new ApiClientError(
        errorMessage(payload, `请求失败（HTTP ${response.status}）`),
        response.status,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    throw new ApiClientError(
      error instanceof DOMException && error.name === "AbortError"
        ? "请求超时，请稍后重试"
        : "无法连接服务，请检查网络后重试",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function registerAccount(payload: {
  display_name: string;
  email: string;
  password: string;
}): Promise<User> {
  return request<User>("/api/v1/auth/register", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function loginAccount(payload: { email: string; password: string }): Promise<User> {
  return request<User>("/api/v1/auth/login", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function logoutAccount(): Promise<void> {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

export function getCurrentUser(): Promise<User> {
  return request<User>("/api/v1/auth/me");
}

export function listFamilies(): Promise<Family[]> {
  return request<Family[]>("/api/v1/families");
}

export function createFamily(name: string): Promise<Family> {
  return request<Family>("/api/v1/families", {
    method: "POST",
    body: jsonBody({ name }),
  });
}

export function listChildren(familyId: string): Promise<Child[]> {
  return request<Child[]>(`/api/v1/families/${familyId}/children`);
}

export function createChild(
  familyId: string,
  payload: {
    display_name: string;
    nickname?: string | null;
    birth_date: string;
    gender?: ChildGender | null;
  },
): Promise<Child> {
  return request<Child>(`/api/v1/families/${familyId}/children`, {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function getAdminOverview(): Promise<AdminOverview> {
  return request<AdminOverview>("/api/v1/admin/overview");
}

export function listAdminCharacters(filters: {
  search?: string;
  enabled?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<CharacterPage> {
  const query = new URLSearchParams();
  if (filters.search) query.set("search", filters.search);
  if (filters.enabled !== undefined) query.set("enabled", String(filters.enabled));
  query.set("page", String(filters.page ?? 1));
  query.set("page_size", String(filters.pageSize ?? 20));
  return request<CharacterPage>(`/api/v1/admin/characters?${query.toString()}`);
}

export function createAdminCharacter(payload: CharacterInput): Promise<ChineseCharacter> {
  return request<ChineseCharacter>("/api/v1/admin/characters", {
    method: "POST",
    body: jsonBody(payload),
  });
}

export function updateAdminCharacter(
  id: string,
  payload: Partial<CharacterInput> & { status?: CharacterStatus },
): Promise<ChineseCharacter> {
  return request<ChineseCharacter>(`/api/v1/admin/characters/${id}`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function importStarterCharacters(): Promise<ImportReport> {
  return request<ImportReport>("/api/v1/admin/characters/import-starter", {
    method: "POST",
  });
}

export function getCharacterMasterySummary(childId: string): Promise<CharacterMasterySummary> {
  return request<CharacterMasterySummary>(`/api/v1/children/${childId}/characters/summary`);
}

export function listCharacterMastery(
  childId: string,
  filters: {
    search?: string;
    masteryLevel?: MasteryLevel;
    priority?: boolean;
    page?: number;
    pageSize?: number;
  },
): Promise<CharacterMasteryPage> {
  const query = new URLSearchParams();
  if (filters.search) query.set("search", filters.search);
  if (filters.masteryLevel) query.set("mastery_level", filters.masteryLevel);
  if (filters.priority !== undefined) query.set("priority", String(filters.priority));
  query.set("page", String(filters.page ?? 1));
  query.set("page_size", String(filters.pageSize ?? 20));
  return request<CharacterMasteryPage>(
    `/api/v1/children/${childId}/characters?${query.toString()}`,
  );
}

export function getCharacterMasteryDetail(
  childId: string,
  knowledgePointId: string,
): Promise<CharacterMasteryDetail> {
  return request<CharacterMasteryDetail>(
    `/api/v1/children/${childId}/characters/${knowledgePointId}`,
  );
}

export function getCharacterRecommendations(
  childId: string,
  mode: "new" | "assessment",
  limit = 5,
): Promise<CharacterRecommendation[]> {
  return request<CharacterRecommendation[]>(
    `/api/v1/children/${childId}/characters/recommendations?mode=${mode}&limit=${limit}`,
  );
}

export function createLearningSession(
  childId: string,
  knowledgePointIds: string[],
): Promise<EvidenceSession> {
  return request<EvidenceSession>(`/api/v1/children/${childId}/learning-sessions`, {
    method: "POST",
    body: jsonBody({
      status: "completed",
      source: "parent_assisted",
      items: knowledgePointIds.map((knowledge_point_id) => ({
        knowledge_point_id,
        activity_type: "introduced",
      })),
    }),
  });
}

export function createAssessmentSession(
  childId: string,
  items: Array<{
    knowledge_point_id: string;
    outcome: "correct" | "hinted_correct" | "uncertain" | "incorrect";
    response_time_ms: number;
    hint_used?: boolean;
  }>,
): Promise<EvidenceSession> {
  return request<EvidenceSession>(`/api/v1/children/${childId}/assessment-sessions`, {
    method: "POST",
    body: jsonBody({ status: "completed", source: "quick_recognition", items }),
  });
}

export function updateCharacterPriority(
  childId: string,
  knowledgePointId: string,
  isPriority: boolean,
): Promise<CharacterMasteryState> {
  return request<CharacterMasteryState>(
    `/api/v1/children/${childId}/characters/${knowledgePointId}/priority`,
    { method: "PATCH", body: jsonBody({ is_priority: isPriority }) },
  );
}
