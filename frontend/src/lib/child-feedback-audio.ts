"use client";

type FeedbackNote = { frequency: number; durationMs: number; delayMs?: number };

type WebkitAudioWindow = Window &
  typeof globalThis & { webkitAudioContext?: typeof AudioContext };

/**
 * Owns the short child feedback queue so a result tone and the next question's
 * speech never compete. Web Audio is deliberately optional: evidence saving
 * and navigation continue when the browser cannot create an AudioContext.
 */
export class ChildFeedbackAudio {
  private context: AudioContext | null = null;
  private generation = 0;
  private activeOscillators = new Set<OscillatorNode>();

  cancel(): void {
    this.generation += 1;
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    for (const oscillator of this.activeOscillators) {
      try {
        oscillator.stop();
      } catch {
        // An oscillator that already ended is safe to ignore.
      }
    }
    this.activeOscillators.clear();
  }

  speakInstruction(text: string): boolean {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
    this.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 0.82;
    window.speechSynthesis.speak(utterance);
    return true;
  }

  playCorrectFeedback(): Promise<void> {
    return this.playNotes([
      { frequency: 659.25, durationMs: 120 },
      { frequency: 880, durationMs: 150, delayMs: 45 },
    ]);
  }

  playIncorrectFeedback(): Promise<void> {
    return this.playNotes([
      { frequency: 392, durationMs: 130 },
      { frequency: 349.23, durationMs: 170, delayMs: 55 },
    ]);
  }

  playCompletedFeedback(): Promise<void> {
    return this.playNotes([
      { frequency: 523.25, durationMs: 110 },
      { frequency: 659.25, durationMs: 110, delayMs: 45 },
      { frequency: 783.99, durationMs: 190, delayMs: 45 },
    ]);
  }

  private getContext(): AudioContext | null {
    if (typeof window === "undefined") return null;
    const AudioContextClass =
      window.AudioContext ?? (window as WebkitAudioWindow).webkitAudioContext;
    if (!AudioContextClass) return null;
    this.context ??= new AudioContextClass();
    return this.context;
  }

  private async playNotes(notes: FeedbackNote[]): Promise<void> {
    this.cancel();
    const generation = this.generation;
    const context = this.getContext();
    if (!context) return;
    try {
      if (context.state === "suspended") await context.resume();
      let cursor = context.currentTime + 0.02;
      let totalMs = 20;
      for (const note of notes) {
        const delayMs = note.delayMs ?? 0;
        cursor += delayMs / 1000;
        totalMs += delayMs + note.durationMs;
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = note.frequency;
        gain.gain.setValueAtTime(0.0001, cursor);
        gain.gain.exponentialRampToValueAtTime(0.16, cursor + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, cursor + note.durationMs / 1000);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(cursor);
        oscillator.stop(cursor + note.durationMs / 1000 + 0.02);
        this.activeOscillators.add(oscillator);
        oscillator.addEventListener("ended", () => this.activeOscillators.delete(oscillator), {
          once: true,
        });
        cursor += note.durationMs / 1000;
      }
      await new Promise<void>((resolve) => window.setTimeout(resolve, totalMs + 40));
      if (generation !== this.generation) return;
    } catch {
      // Audio is enhancement-only; the visual feedback and learning flow continue.
    }
  }
}

export const childFeedbackAudio = new ChildFeedbackAudio();

export const playCorrectFeedback = () => childFeedbackAudio.playCorrectFeedback();
export const playIncorrectFeedback = () => childFeedbackAudio.playIncorrectFeedback();
export const playCompletedFeedback = () => childFeedbackAudio.playCompletedFeedback();

