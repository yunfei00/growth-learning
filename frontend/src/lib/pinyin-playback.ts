const HAN_CHARACTER = /[\u3400-\u9fff]/u;

export type PinyinPlayback =
  | { mode: "curated"; url: string }
  | { mode: "tts_fallback"; speechText: string }
  | { mode: "missing" };

export type PinyinAudioDescriptor = {
  display_text: string;
  audio: {
    mode: "curated" | "tts_fallback" | "missing";
    audio_url: string | null;
    speech_text: string | null;
  };
};

export function resolvePinyinPlayback(
  item: PinyinAudioDescriptor,
  apiBaseUrl = "",
): PinyinPlayback {
  if (item.audio.mode === "curated" && item.audio.audio_url) {
    return { mode: "curated", url: `${apiBaseUrl}${item.audio.audio_url}` };
  }
  const speechText = item.audio.speech_text?.trim() ?? "";
  if (item.audio.mode === "tts_fallback" && HAN_CHARACTER.test(speechText)) {
    return { mode: "tts_fallback", speechText };
  }
  return { mode: "missing" };
}
