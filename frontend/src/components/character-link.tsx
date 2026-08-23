"use client";

import Link from "next/link";
import { type ReactNode, useEffect } from "react";

import {
  buildCharacterLearningHref,
  type CharacterLearningContext,
} from "@/lib/character-navigation";
import { activateChineseSpeech } from "@/lib/speech";

const SCROLL_KEY = "growth-learning:character-return-scroll";

export function CharacterLink({
  knowledgePointId,
  children,
  className,
  context,
  speakText,
  wrapperClassName,
}: {
  knowledgePointId: string;
  children: ReactNode;
  className?: string;
  context?: CharacterLearningContext;
  speakText?: string;
  wrapperClassName?: string;
}) {
  useEffect(() => {
    const stored = window.sessionStorage.getItem(SCROLL_KEY);
    if (!stored) return;
    try {
      const marker = JSON.parse(stored) as { location: string; scrollY: number };
      const location = `${window.location.pathname}${window.location.search}`;
      if (marker.location === location) {
        window.sessionStorage.removeItem(SCROLL_KEY);
        window.requestAnimationFrame(() => window.scrollTo({ top: marker.scrollY }));
      }
    } catch {
      window.sessionStorage.removeItem(SCROLL_KEY);
    }
  }, []);

  const link = (
    <Link
      className={className}
      href={buildCharacterLearningHref(knowledgePointId, context)}
      onClick={() => {
        window.sessionStorage.setItem(
          SCROLL_KEY,
          JSON.stringify({
            location: `${window.location.pathname}${window.location.search}`,
            scrollY: window.scrollY,
          }),
        );
      }}
    >
      {children}
    </Link>
  );
  if (!speakText) return link;
  return (
    <span className={`character-link-with-audio ${wrapperClassName ?? ""}`.trim()}>
      {link}
      <button
        aria-label={`朗读${speakText}`}
        className="character-audio-button"
        onClick={(event) => activateChineseSpeech(event, speakText)}
        type="button"
      >
        <span aria-hidden="true">🔊</span>
      </button>
    </span>
  );
}
