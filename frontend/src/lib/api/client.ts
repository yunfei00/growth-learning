const DEFAULT_API_PORT = "8000";
const REQUEST_TIMEOUT_MS = 8_000;

export type User = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
