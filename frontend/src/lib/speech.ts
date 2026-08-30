type SpeechUtteranceLike = {
  lang: string;
  rate: number;
  onend?: (() => void) | null;
  onerror?: (() => void) | null;
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
  const utteranceFactory: ((value: string) => SpeechUtteranceLike) | null =
    createUtterance === undefined
      ? typeof SpeechSynthesisUtterance === "undefined"
        ? null
        : (utteranceText: string) => new SpeechSynthesisUtterance(utteranceText) as unknown as SpeechUtteranceLike
      : createUtterance;
  if (!value || !speechTarget || !utteranceFactory) return false;
  speechTarget.cancel();
  const utterance = utteranceFactory(value);
  utterance.lang = "zh-CN";
  utterance.rate = 0.75;
  speechTarget.speak(utterance);
  return true;
}

export function speakChineseAndWait(
  text: string,
  speech?: SpeechSynthesisLike | null,
  createUtterance?: ((value: string) => SpeechUtteranceLike) | null,
  timeoutMs = 5000,
): Promise<boolean> {
  const value = text.trim();
  const speechTarget =
    speech === undefined
      ? typeof window !== "undefined" && "speechSynthesis" in window
        ? (window.speechSynthesis as unknown as SpeechSynthesisLike)
        : null
      : speech;
  const utteranceFactory: ((value: string) => SpeechUtteranceLike) | null =
    createUtterance === undefined
      ? typeof SpeechSynthesisUtterance === "undefined"
        ? null
        : (utteranceText: string) => new SpeechSynthesisUtterance(utteranceText) as unknown as SpeechUtteranceLike
      : createUtterance;
  if (!value || !speechTarget || !utteranceFactory) return Promise.resolve(false);

  speechTarget.cancel();
  const utterance = utteranceFactory(value);
  utterance.lang = "zh-CN";
  utterance.rate = 0.75;
  return new Promise<boolean>((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (typeof window !== "undefined" && timer !== undefined) window.clearTimeout(timer);
      resolve(true);
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    const timer = typeof window !== "undefined"
      ? window.setTimeout(finish, timeoutMs)
      : undefined;
    speechTarget.speak(utterance);
    if (timer === undefined) finish();
  });
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
