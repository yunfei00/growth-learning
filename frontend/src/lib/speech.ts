type SpeechUtteranceLike = {
  lang: string;
  rate: number;
};

type SpeechSynthesisLike = {
  cancel: () => void;
  speak: (utterance: SpeechUtteranceLike) => void;
};

type SpeechEventLike = {
  preventDefault: () => void;
  stopPropagation: () => void;
};

export function speakChinese(
  text: string,
  speech?: SpeechSynthesisLike | null,
  createUtterance?: ((value: string) => SpeechUtteranceLike) | null,
): boolean {
  const value = text.trim();
  const speechTarget =
    speech === undefined
      ? typeof window !== "undefined" && "speechSynthesis" in window
        ? (window.speechSynthesis as unknown as SpeechSynthesisLike)
        : null
      : speech;
  const utteranceFactory =
    createUtterance === undefined
      ? typeof SpeechSynthesisUtterance === "undefined"
        ? null
        : (utteranceText: string) => new SpeechSynthesisUtterance(utteranceText)
      : createUtterance;
  if (!value || !speechTarget || !utteranceFactory) return false;
  speechTarget.cancel();
  const utterance = utteranceFactory(value);
  utterance.lang = "zh-CN";
  utterance.rate = 0.75;
  speechTarget.speak(utterance);
  return true;
}

export function activateChineseSpeech(
  event: SpeechEventLike,
  text: string,
  speech?: SpeechSynthesisLike | null,
  createUtterance?: ((value: string) => SpeechUtteranceLike) | null,
): boolean {
  event.preventDefault();
  event.stopPropagation();
  return speakChinese(text, speech, createUtterance);
}
