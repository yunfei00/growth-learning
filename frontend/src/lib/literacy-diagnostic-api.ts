import {
  getApiBaseUrl,
  type SpeechAlternative,
  type SpeechAttempt,
  type SpeechReviewDecision,
} from "@/lib/api/client";

export type LiteracyDiagnosticOutcome = "correct" | "uncertain" | "incorrect";
export type LiteracyDiagnosticEvaluationMethod = "parent_manual" | "speech_assisted";

export type LiteracyDiagnosticTarget = {
  knowledge_point_id: string;
  character: string;
  pinyin: string;
  position: number;
  sampling_class: string;
  outcome: LiteracyDiagnosticOutcome | null;
  assessment_item_id: string | null;
  response_time_ms: number | null;
  evaluation_method: LiteracyDiagnosticEvaluationMethod | null;
  speech_attempts: SpeechAttempt[];
};

export type LiteracyDiagnosticResult = {
  assessment_session_id: string;
  catalog_size: number;
  catalog_version: string;
  sample_size: number;
  estimated_known: number;
  lower_bound: number;
  upper_bound: number;
  directly_known: number;
  uncertain: number;
  unknown: number;
  untested: number;
  estimation_version: string;
  limitation: string;
  created_at: string;
};

export type LiteracyDiagnosticSession = {
  id: string;
  child_id: string;
  source: "literacy_diagnostic";
  status: "in_progress" | "completed" | "abandoned";
  sampling_method: string;
  sampling_version: string;
  eligible_catalog_size: number;
  catalog_version: string;
  segment_size: number;
  total_segments: number;
  current_segment: number;
  segment_break_due: boolean;
  started_at: string;
  completed_at: string | null;
  total_items: number;
  completed_items: number;
  targets: LiteracyDiagnosticTarget[];
  result: LiteracyDiagnosticResult | null;
};

export type LiteracyDiagnosticHistoryEntry = {
  id: string;
  status: "in_progress" | "completed" | "abandoned";
  started_at: string;
  completed_at: string | null;
  total_items: number;
  completed_items: number;
  directly_known: number;
  uncertain: number;
  unknown: number;
  result: LiteracyDiagnosticResult | null;
};

export type LiteracyDiagnosticOverview = {
  active_session: LiteracyDiagnosticSession | null;
  latest_result: LiteracyDiagnosticResult | null;
  history: LiteracyDiagnosticHistoryEntry[];
  recommended_sample_size: number;
  segment_size: number;
  limitation: string;
  server_asr_enabled: boolean;
  server_asr_provider: string | null;
  server_asr_model: string | null;
};

type ApiErrorPayload = { detail?: string };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new Error(payload?.detail || `请求失败（HTTP ${response.status}）`);
  }
  return (await response.json()) as T;
}

export function getLiteracyDiagnosticOverview(childId: string): Promise<LiteracyDiagnosticOverview> {
  return request(`/api/v1/children/${childId}/literacy-diagnostic/overview`);
}

export function getLiteracyDiagnosticHistory(
  childId: string,
  limit = 20,
): Promise<LiteracyDiagnosticHistoryEntry[]> {
  return request(`/api/v1/children/${childId}/literacy-diagnostic/history?limit=${limit}`);
}

export function startLiteracyDiagnostic(childId: string): Promise<LiteracyDiagnosticSession> {
  return request(`/api/v1/children/${childId}/literacy-diagnostic/start`, { method: "POST" });
}

export function getLiteracyDiagnosticSession(
  childId: string,
  sessionId: string,
): Promise<LiteracyDiagnosticSession> {
  return request(
    `/api/v1/children/${childId}/literacy-diagnostic/sessions/${sessionId}`,
  );
}

export function submitLiteracyDiagnosticItems(
  childId: string,
  sessionId: string,
  items: Array<{
    knowledge_point_id: string;
    outcome: LiteracyDiagnosticOutcome;
    response_time_ms?: number;
    evaluation_method: LiteracyDiagnosticEvaluationMethod;
    speech_attempt_ids?: string[];
  }>,
): Promise<LiteracyDiagnosticSession> {
  return request(
    `/api/v1/children/${childId}/literacy-diagnostic/sessions/${sessionId}/items`,
    { method: "POST", body: JSON.stringify({ items }) },
  );
}

export function createLiteracyDiagnosticSpeechAttempt(
  childId: string,
  sessionId: string,
  payload: {
    knowledge_point_id: string;
    attempt_index: number;
    provider: string;
    transcript?: string | null;
    alternatives?: SpeechAlternative[];
    confidence?: number | null;
    confidence_available?: boolean;
    duration_ms?: number | null;
    decision: SpeechReviewDecision;
    normalized_readings?: string[];
    syllable_match?: boolean | null;
    tone_match?: boolean | null;
    tone_evaluation?: "matched" | "mismatched" | "unavailable";
    explicit_unknown?: boolean;
    provider_metadata?: Record<string, unknown>;
  },
): Promise<SpeechAttempt> {
  return request(
    `/api/v1/children/${childId}/literacy-diagnostic/sessions/${sessionId}/speech-attempts`,
    { method: "POST", body: JSON.stringify({ ...payload, hint_used: false }) },
  );
}

export async function createLiteracyDiagnosticAudioAttempt(
  childId: string,
  sessionId: string,
  payload: {
    knowledge_point_id: string;
    attempt_index: number;
    audio: Blob;
    capture_duration_ms?: number;
  },
): Promise<SpeechAttempt> {
  const form = new FormData();
  form.set("knowledge_point_id", payload.knowledge_point_id);
  form.set("attempt_index", String(payload.attempt_index));
  if (typeof payload.capture_duration_ms === "number") {
    form.set("capture_duration_ms", String(payload.capture_duration_ms));
  }
  const extension = payload.audio.type.includes("mp4")
    ? "m4a"
    : payload.audio.type.includes("ogg")
      ? "ogg"
      : payload.audio.type.includes("wav")
        ? "wav"
        : "webm";
  form.set("audio", payload.audio, `diagnostic-utterance.${extension}`);
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/children/${childId}/literacy-diagnostic/sessions/${sessionId}/audio-attempts`,
    {
      method: "POST",
      body: form,
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
    },
  );
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new Error(body?.detail || `请求失败（HTTP ${response.status}）`);
  }
  return (await response.json()) as SpeechAttempt;
}