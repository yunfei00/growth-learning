import { getApiBaseUrl, type PinyinItemDetail } from "@/lib/api/client";
import { resolvePinyinPlayback } from "@/lib/pinyin-playback";
import { speakChinese } from "@/lib/speech";

export async function playPinyinAudio(item: PinyinItemDetail): Promise<boolean> {
  const playback = resolvePinyinPlayback(item, getApiBaseUrl());
  if (playback.mode === "curated") {
    const audio = new Audio(playback.url);
    await audio.play();
    return true;
  }
  if (playback.mode === "tts_fallback") {
    return speakChinese(playback.speechText);
  }
  return false;
}
