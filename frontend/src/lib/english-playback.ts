import type { EnglishAudio } from "@/lib/api/client";

export function playEnglishAudio(audio: EnglishAudio): boolean {
  if (!audio.available || typeof window === "undefined") return false;
  if (audio.audio_url) {
    const player = new Audio(audio.audio_url);
    void player.play();
    return true;
  }
  if (!audio.speech_text || !("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(audio.speech_text);
  utterance.lang = audio.accent || "en-US";
  utterance.rate = 0.72;
  window.speechSynthesis.speak(utterance);
  return true;
}
