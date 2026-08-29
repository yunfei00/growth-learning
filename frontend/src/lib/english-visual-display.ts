import { withAppBasePath } from "./public-assets.ts";

export type StaticEnglishVisual = {
  image_url: string | null;
  visual_key: string | null;
};

export type StaticEnglishVisualDisplay =
  | { kind: "image"; src: string }
  | { kind: "fallback"; symbol: string };

export function resolveStaticEnglishVisual(
  visual: StaticEnglishVisual,
  imageFailed = false,
  basePath?: string,
): StaticEnglishVisualDisplay {
  if (visual.image_url && !imageFailed) {
    return { kind: "image", src: withAppBasePath(visual.image_url, basePath) };
  }
  return { kind: "fallback", symbol: visual.visual_key?.trim() || "🔊" };
}
