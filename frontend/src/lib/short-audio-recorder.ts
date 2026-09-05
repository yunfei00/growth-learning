"use client";

export type ShortAudioRecording = {
  blob: Blob;
  mimeType: string;
  durationMs: number;
};

export type ShortAudioRecorder = {
  supported: boolean;
  unavailableReason: "insecure_context" | "not_supported" | null;
  record: (options?: { durationMs?: number }) => Promise<ShortAudioRecording>;
  abort: () => void;
};

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
  "audio/mp4",
];

export function resolveShortAudioRecorderAvailability({
  secureContext,
  hasMediaDevices,
  hasMediaRecorder,
}: {
  secureContext: boolean;
  hasMediaDevices: boolean;
  hasMediaRecorder: boolean;
}): Pick<ShortAudioRecorder, "supported" | "unavailableReason"> {
  if (!secureContext) return { supported: false, unavailableReason: "insecure_context" };
  if (!hasMediaDevices || !hasMediaRecorder) {
    return { supported: false, unavailableReason: "not_supported" };
  }
  return { supported: true, unavailableReason: null };
}

function preferredMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return MIME_CANDIDATES.find((value) => MediaRecorder.isTypeSupported(value)) ?? "";
}

export function createShortAudioRecorder(): ShortAudioRecorder {
  let activeRecorder: MediaRecorder | null = null;
  let activeStream: MediaStream | null = null;
  let timer: number | null = null;
  let rejectCurrent: ((reason?: unknown) => void) | null = null;
  const availability = resolveShortAudioRecorderAvailability({
    secureContext: typeof window !== "undefined" && window.isSecureContext,
    hasMediaDevices:
      typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia),
    hasMediaRecorder: typeof MediaRecorder !== "undefined",
  });

  const cleanup = () => {
    if (timer !== null && typeof window !== "undefined") window.clearTimeout(timer);
    timer = null;
    activeStream?.getTracks().forEach((track) => track.stop());
    activeStream = null;
    activeRecorder = null;
    rejectCurrent = null;
  };

  const abort = () => {
    try {
      if (activeRecorder && activeRecorder.state !== "inactive") activeRecorder.stop();
    } catch {
      // Browser may throw if recording already ended.
    }
    const reject = rejectCurrent;
    cleanup();
    reject?.({ code: "aborted" as const });
  };

  return {
    ...availability,
    record: async ({ durationMs = 2600 } = {}) => {
      if (!availability.supported || typeof window === "undefined") {
        throw { code: availability.unavailableReason ?? "not_supported" };
      }
      abort();
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });
      } catch (error) {
        throw { code: "not_allowed", cause: error };
      }
      activeStream = stream;
      const mimeType = preferredMimeType();
      let recorder: MediaRecorder;
      try {
        recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      } catch (error) {
        cleanup();
        throw { code: "not_supported", cause: error };
      }
      activeRecorder = recorder;
      const chunks: BlobPart[] = [];
      const startedAt = performance.now();
      return await new Promise<ShortAudioRecording>((resolve, reject) => {
        rejectCurrent = reject;
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunks.push(event.data);
        };
        recorder.onerror = () => {
          cleanup();
          reject({ code: "recording_error" });
        };
        recorder.onstop = () => {
          const actualMimeType = recorder.mimeType || mimeType || "audio/webm";
          const blob = new Blob(chunks, { type: actualMimeType });
          const elapsed = Math.max(0, Math.round(performance.now() - startedAt));
          cleanup();
          if (blob.size === 0) {
            reject({ code: "no_speech" });
            return;
          }
          resolve({ blob, mimeType: actualMimeType, durationMs: elapsed });
        };
        try {
          recorder.start();
        } catch (error) {
          cleanup();
          reject({ code: "recording_error", cause: error });
          return;
        }
        timer = window.setTimeout(() => {
          try {
            if (recorder.state !== "inactive") recorder.stop();
          } catch {
            cleanup();
            reject({ code: "recording_error" });
          }
        }, durationMs);
      });
    },
    abort,
  };
}
