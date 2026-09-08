const SHORT_HAN_TARGET = /^[\u3400-\u9fff]$/u;

export type PinyinPlayback =
  | { mode: "curated"; url: string }
  | { mode: "tts_fallback"; speechText: string }
  | { mode: "missing" };

export type PinyinAudioDescriptor = {
  kind?: "initial" | "final" | "tone" | "whole";
  audio: {
    mode: "curated" | "tts_fallback" | "missing";
    audio_url: string | null;
    speech_text: string | null;
    purpose: "target_pronunciation";
    target_pronunciation: string;
  };
};

export function resolvePinyinPlayback(
  item: PinyinAudioDescriptor,
  apiBaseUrl = "",
): PinyinPlayback {
  if (item.audio.purpose !== "target_pronunciation" || !item.audio.target_pronunciation.trim()) {
    return { mode: "missing" };
  }
  if (item.audio.mode === "curated" && item.audio.audio_url) {
    return { mode: "curated", url: `${apiBaseUrl}${item.audio.audio_url}` };
  }
  if (item.kind === "tone") {
    return { mode: "missing" };
  }
  const speechText = item.audio.speech_text?.trim() ?? "";
  if (item.audio.mode === "tts_fallback" && SHORT_HAN_TARGET.test(speechText)) {
    return { mode: "tts_fallback", speechText };
  }
  return { mode: "missing" };
}
