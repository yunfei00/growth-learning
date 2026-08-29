"use client";

import Image from "next/image";
import { useState } from "react";

import type { EnglishVisual } from "@/lib/api/client";
import { resolveStaticEnglishVisual } from "@/lib/english-visual-display";

export function EnglishVisualCard({
  visual,
  label,
  compact = false,
}: {
  visual: EnglishVisual;
  label: string;
  compact?: boolean;
}) {
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);

  if (visual.visual_type === "static_image") {
    const display = resolveStaticEnglishVisual(
      visual,
      Boolean(visual.image_url && failedImageUrl === visual.image_url),
    );
    if (display.kind === "fallback") {
      return (
        <span
          aria-label={label}
          className={`english-visual symbol visual-fallback${compact ? " compact" : ""}`}
          data-visual-fallback="true"
          role="img"
        >
          {display.symbol}
        </span>
      );
    }
    return (
      <span className={`english-visual static${compact ? " compact" : ""}`}>
        <Image
          alt={label}
          height={compact ? 96 : 220}
          onError={() => setFailedImageUrl(visual.image_url)}
          src={display.src}
          unoptimized
          width={compact ? 96 : 220}
        />
      </span>
    );
  }
  if (visual.visual_type === "color_swatch") {
    return (
      <span
        aria-label={label}
        className={`english-visual color${compact ? " compact" : ""}`}
        style={{ backgroundColor: visual.visual_key ?? "#d8e7dc" }}
      />
    );
  }
  if (visual.visual_type === "shape") {
    return (
      <span className={`english-visual shape shape-${visual.visual_key ?? "circle"}${compact ? " compact" : ""}`}>
        <i aria-hidden="true" />
        <span className="sr-only">{label}</span>
      </span>
    );
  }
  return (
    <span aria-label={label} className={`english-visual symbol${compact ? " compact" : ""}`} role="img">
      {visual.visual_key ?? "🔊"}
    </span>
  );
}
