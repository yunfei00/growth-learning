import Image from "next/image";

import type { EnglishVisual } from "@/lib/api/client";

export function EnglishVisualCard({
  visual,
  label,
  compact = false,
}: {
  visual: EnglishVisual;
  label: string;
  compact?: boolean;
}) {
  if (visual.visual_type === "static_image" && visual.image_url) {
    return (
      <span className={`english-visual static${compact ? " compact" : ""}`}>
        <Image alt={label} height={compact ? 96 : 220} src={visual.image_url} unoptimized width={compact ? 96 : 220} />
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
    <span aria-label={label} className={`english-visual symbol${compact ? " compact" : ""}`}>
      {visual.visual_key ?? "🔊"}
    </span>
  );
}
