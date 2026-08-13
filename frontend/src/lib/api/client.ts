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

export type LearningSettings = {
  max_new_characters_per_day: number;
  daily_review_capacity: number;
  weekly_assessment_enabled: boolean;
  monthly_assessment_enabled: boolean;
  timezone: string;
};

export type DailyPlanItem = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  common_words: string[];
  simple_meaning: string | null;
  example_sentence: string | null;
  item_kind: "new" | "review";
  status: "pending" | "completed";
  position: number;
  selection_reason: string;
};

export type DailyPlan = {
  id: string;
  child_id: string;
  plan_date: string;
  timezone: string;
  recommended_new_count: number;
  review_count: number;
  due_count: number;
  estimated_backlog_days: number;
  recommendation_reason: string;
  new_completed_count: number;
  review_completed_count: number;
  status: "pending" | "in_progress" | "completed";
  recent_independent_correct_rate: number | null;
  weekly_status: string;
  monthly_status: string;
  literacy_status: string;
  literacy_estimate: number | null;
  literacy_catalog_size: number;
  items: DailyPlanItem[];
  reading: DailyReadingTask;
};

export type DailyReadingTask = {
  status: "needs_story" | "pending" | "in_progress" | "completed";
  target_count: number;
  story_version_id: string | null;
  reading_session_id: string | null;
  title: string | null;
};

export type AssessmentSource =
  | "quick_test"
  | "daily_review"
  | "weekly_check"
  | "monthly_assessment";

export type AssessmentOutcome = "correct" | "hinted_correct" | "uncertain" | "incorrect";

export type AssessmentTarget = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  position: number;
  sampling_class: string;
  outcome: AssessmentOutcome | null;
  response_time_ms: number | null;
};

export type PlannedAssessment = {
  id: string;
  child_id: string;
  source: AssessmentSource;
  status: "in_progress" | "completed" | "abandoned";
  sampling_method: string;
  sampling_version: string;
  eligible_catalog_size: number;
  started_at: string;
  completed_at: string | null;
  total_items: number;
  completed_items: number;
  targets: AssessmentTarget[];
};

export type AssessmentHistoryEntry = {
  id: string;
  source: AssessmentSource;
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  item_count: number;
  correct: number;
  hinted_correct: number;
  uncertain: number;
  incorrect: number;
};

export type LiteracyEstimate = {
  id: string | null;
  assessment_session_id: string | null;
  catalog_size: number;
  sample_size: number;
  known_count: number;
  unknown_count: number;
  sampling_method: string | null;
  sampling_version: string | null;
  estimate: number | null;
  lower_bound: number | null;
  upper_bound: number | null;
  is_sufficient: boolean;
  estimation_version: string;
  limitation: string;
  created_at: string | null;
};

export type StoryDifficulty = "beginner" | "normal" | "challenge";

export type StoryTarget = {
  knowledge_point_id: string;
  character: string;
  mastery_level: MasteryLevel;
  is_priority: boolean;
};

export type ReadingContext = {
  child_id: string;
  age_band: string;
  provider_configured: boolean;
  provider: string;
  model: string;
  recommended_difficulty: StoryDifficulty | null;
  strong_known_count: number;
  usable_recognizing_count: number;
  automatic_targets: StoryTarget[];
  safe_themes: string[];
  catalog_size: number;
  catalog_limitation: string;
  feasibility_message: string | null;
};

export type ReadingQuestion = {
  id: string;
  position: number;
  question: string;
  options: string[];
};

export type CharacterGlossary = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  simple_meaning: string | null;
  common_words: string[];
};

export type StoryVersion = {
  id: string;
  story_id: string;
  version_number: number;
  title: string;
  paragraphs: string[];
  summary: string | null;
  theme: string;
  custom_theme: string | null;
  difficulty: StoryDifficulty;
  requested_known_coverage: number;
  actual_strong_known_coverage: number;
  actual_usable_known_coverage: number;
  actual_target_coverage: number;
  actual_unexpected_coverage: number;
  unique_known_coverage: number;
  total_han_occurrences: number;
  unique_han_count: number;
  unexpected_characters: string[];
  target_characters: string[];
  snapshot_at: string;
  coverage_policy_version: string;
  analyzer_version: string;
  prompt_version: string;
  provider: string;
  model: string;
  questions: ReadingQuestion[];
  glossary: CharacterGlossary[];
  created_at: string;
};

export type StoryGenerationResult = {
  generation_run_id: string;
  status: "succeeded";
  attempt_count: number;
  version: StoryVersion;
};

export type StoryListItem = {
  story_id: string;
  story_version_id: string;
  title: string;
  theme: string;
  difficulty: StoryDifficulty;
  actual_known_coverage: number;
  target_characters: string[];
  generated_at: string;
  reading_status: "in_progress" | "completed" | "abandoned" | null;
  reading_mode: "independent" | "with_help" | null;
  comprehension_answered: number;
  comprehension_total: number;
};

export type StoryPage = {
  items: StoryListItem[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type ReadingAnswer = {
  question_id: string;
  selected_option_index: number;
  outcome: "correct" | "with_help" | "partial" | "incorrect";
  answered_at: string;
};

export type ReadingSession = {
  id: string;
  child_id: string;
  story_version_id: string;
  reading_mode: "independent" | "with_help";
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  parent_note: string | null;
  answers: ReadingAnswer[];
  story_exposure_count: number;
};

export type ReadingSummary = {
  stories_read_this_week: number;
  independent_this_week: number;
  with_help_this_week: number;
  comprehension_correct: number;
  comprehension_answered: number;
  comprehension_message: string;
  target_exposure_count: number;
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

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
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

export function getLearningSettings(childId: string): Promise<LearningSettings> {
  return request<LearningSettings>(`/api/v1/children/${childId}/learning-settings`);
}

export function updateLearningSettings(
  childId: string,
  payload: Partial<LearningSettings>,
): Promise<LearningSettings> {
  return request<LearningSettings>(`/api/v1/children/${childId}/learning-settings`, {
    method: "PATCH",
    body: jsonBody(payload),
  });
}

export function getTodayPlan(childId: string): Promise<DailyPlan> {
  return request<DailyPlan>(`/api/v1/children/${childId}/today`);
}

export function startPlannedAssessment(
  childId: string,
  source: "daily_review" | "weekly_check" | "monthly_assessment",
): Promise<PlannedAssessment> {
  const route = {
    daily_review: "reviews",
    weekly_check: "weekly-check",
    monthly_assessment: "monthly-assessment",
  }[source];
  return request<PlannedAssessment>(`/api/v1/children/${childId}/${route}/start`, {
    method: "POST",
  });
}

export function getPlannedAssessment(
  childId: string,
  sessionId: string,
): Promise<PlannedAssessment> {
  return request<PlannedAssessment>(
    `/api/v1/children/${childId}/planned-assessments/${sessionId}`,
  );
}

export function submitPlannedAssessment(
  childId: string,
  sessionId: string,
  payload: {
    items: Array<{
      knowledge_point_id: string;
      outcome: AssessmentOutcome;
      response_time_ms: number;
      hint_used?: boolean;
    }>;
    complete?: boolean;
  },
): Promise<PlannedAssessment> {
  return request<PlannedAssessment>(
    `/api/v1/children/${childId}/planned-assessments/${sessionId}/items`,
    { method: "POST", body: jsonBody(payload) },
  );
}

export function getAssessmentHistory(childId: string): Promise<AssessmentHistoryEntry[]> {
  return request<AssessmentHistoryEntry[]>(`/api/v1/children/${childId}/assessment-history`);
}

export function getLiteracyEstimate(childId: string): Promise<LiteracyEstimate> {
  return request<LiteracyEstimate>(`/api/v1/children/${childId}/literacy-estimate`);
}

export function getReadingContext(childId: string): Promise<ReadingContext> {
  return request<ReadingContext>(`/api/v1/children/${childId}/reading-context`);
}

export function generateStory(
  childId: string,
  payload: {
    difficulty: StoryDifficulty;
    theme: string;
    custom_theme?: string | null;
    target_knowledge_point_ids?: string[];
    request_key?: string;
    story_id?: string;
  },
): Promise<StoryGenerationResult> {
  return request<StoryGenerationResult>(
    `/api/v1/children/${childId}/stories/generate`,
    { method: "POST", body: jsonBody(payload) },
    90_000,
  );
}

export function listStories(childId: string, page = 1): Promise<StoryPage> {
  return request<StoryPage>(`/api/v1/children/${childId}/stories?page=${page}&page_size=12`);
}

export function getStoryVersion(childId: string, versionId: string): Promise<StoryVersion> {
  return request<StoryVersion>(`/api/v1/children/${childId}/story-versions/${versionId}`);
}

export function startReading(
  childId: string,
  versionId: string,
  readingMode: "independent" | "with_help",
): Promise<ReadingSession> {
  return request<ReadingSession>(
    `/api/v1/children/${childId}/story-versions/${versionId}/reading/start`,
    { method: "POST", body: jsonBody({ reading_mode: readingMode }) },
  );
}

export function submitReadingAnswers(
  childId: string,
  sessionId: string,
  answers: Array<{
    question_id: string;
    selected_option_index: number;
    outcome: "correct" | "with_help" | "partial" | "incorrect";
  }>,
): Promise<ReadingSession> {
  return request<ReadingSession>(
    `/api/v1/children/${childId}/reading-sessions/${sessionId}/answers`,
    { method: "POST", body: jsonBody({ answers }) },
  );
}

export function completeReading(
  childId: string,
  sessionId: string,
  payload: { duration_seconds?: number; parent_note?: string | null },
): Promise<ReadingSession> {
  return request<ReadingSession>(
    `/api/v1/children/${childId}/reading-sessions/${sessionId}/complete`,
    { method: "POST", body: jsonBody(payload) },
  );
}

export function getReadingSummary(childId: string): Promise<ReadingSummary> {
  return request<ReadingSummary>(`/api/v1/children/${childId}/reading-summary`);
}
