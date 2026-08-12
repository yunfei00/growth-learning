const DEFAULT_API_PORT = "8000";
const REQUEST_TIMEOUT_MS = 5_000;

export type HealthResponse = {
  status: "ok";
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiClientError(`API request failed with status ${response.status}`, response.status);
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    throw new ApiClientError("Unable to reach the API");
  } finally {
    window.clearTimeout(timeout);
  }
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { cache: "no-store" });
}
