"use client";

export type SpeechAlternative = { transcript: string; confidence: number | null };

export type SpeechRecognitionResult = {
  transcript: string;
  alternatives: SpeechAlternative[];
  confidence: number | null;
  confidence_available: boolean;
  language: string;
  provider: "browser_speech_recognition";
};

export type SpeechRecognitionErrorCode =
  | "not_supported"
  | "insecure_context"
  | "not_allowed"
  | "no_speech"
  | "network"
  | "aborted"
  | "unknown";

export type SpeechRecognitionProvider = {
  supported: boolean;
  unavailableReason: "not_supported" | "insecure_context" | null;
  start: (options?: { lang?: string; timeoutMs?: number }) => Promise<SpeechRecognitionResult>;
  stop: () => void;
  abort: () => void;
};

type BrowserRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string; confidence?: number }>> }) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
};

type BrowserWindow = Window & {
  SpeechRecognition?: new () => BrowserRecognition;
  webkitSpeechRecognition?: new () => BrowserRecognition;
};

function errorCode(value: string | undefined): SpeechRecognitionErrorCode {
  if (value === "not-allowed" || value === "service-not-allowed") return "not_allowed";
  if (value === "no-speech") return "no_speech";
  if (value === "network") return "network";
  if (value === "aborted") return "aborted";
  return "unknown";
}

export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  const browserWindow = window as BrowserWindow;
  return Boolean(
    window.isSecureContext
      && (browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition),
  );
}

export function createBrowserSpeechRecognitionProvider(): SpeechRecognitionProvider {
  let recognition: BrowserRecognition | null = null;
  let timer: number | null = null;
  let rejectCurrent: ((reason: unknown) => void) | null = null;
  const supported = isSpeechRecognitionSupported();
  const browserWindow = typeof window === "undefined" ? null : window as BrowserWindow;
  const hasRecognitionApi = Boolean(
    browserWindow?.SpeechRecognition ?? browserWindow?.webkitSpeechRecognition,
  );
  const unavailableReason = supported
    ? null
    : hasRecognitionApi && typeof window !== "undefined" && !window.isSecureContext
      ? "insecure_context" as const
      : "not_supported" as const;

  const clear = () => {
    if (timer !== null) window.clearTimeout(timer);
    timer = null;
    rejectCurrent = null;
  };

  const abort = () => {
    clear();
    try {
      recognition?.abort();
    } catch {
      // Browsers can throw when abort is called after an onend event.
    }
    recognition = null;
  };

  return {
    supported,
    unavailableReason,
    start: ({ lang = "zh-CN", timeoutMs = 5000 } = {}) => {
      if (!supported || typeof window === "undefined") {
        return Promise.reject({ code: unavailableReason });
      }
      abort();
      const browserWindow = window as BrowserWindow;
      const Recognition = browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition;
      if (!Recognition) return Promise.reject({ code: "not_supported" as const });
      const instance = new Recognition();
      recognition = instance;
      instance.lang = lang;
      instance.continuous = false;
      instance.interimResults = false;
      instance.maxAlternatives = 5;
      return new Promise<SpeechRecognitionResult>((resolve, reject) => {
        rejectCurrent = reject;
        const finish = (callback: () => void) => {
          clear();
          if (recognition === instance) recognition = null;
          callback();
        };
        instance.onresult = (event) => {
          const first = event.results[0];
          const values: SpeechAlternative[] = [];
          if (first) {
            for (let index = 0; index < first.length; index += 1) {
              const result = first[index];
              if (!result?.transcript) continue;
              values.push({
                transcript: result.transcript.trim(),
                confidence: typeof result.confidence === "number" ? result.confidence : null,
              });
            }
          }
          const primary = values[0];
          finish(() => resolve({
            transcript: primary?.transcript ?? "",
            alternatives: values,
            confidence: primary?.confidence ?? null,
            confidence_available: values.some((value) => value.confidence !== null),
            language: lang,
            provider: "browser_speech_recognition",
          }));
        };
        instance.onerror = (event) => {
          finish(() => reject({ code: errorCode(event.error) }));
        };
        instance.onend = () => {
          if (rejectCurrent) finish(() => reject({ code: "no_speech" as const }));
        };
        timer = window.setTimeout(() => {
          try { instance.stop(); } catch { /* handled by onend */ }
          finish(() => reject({ code: "no_speech" as const }));
        }, timeoutMs);
        try {
          instance.start();
        } catch {
          finish(() => reject({ code: "unknown" as const }));
        }
      });
    },
    stop: () => {
      try { recognition?.stop(); } catch { /* no-op */ }
    },
    abort,
  };
}
