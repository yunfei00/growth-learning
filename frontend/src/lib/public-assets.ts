function normalizedBasePath(basePath: string): string {
  const trimmed = basePath.trim();
  if (!trimmed || trimmed === "/") return "";
  const withLeadingSlash = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return withLeadingSlash.replace(/\/+$/, "");
}

/**
 * Prefix a root-relative file from `public/` with the configured Next.js basePath.
 * API URLs deliberately do not use this helper.
 */
export function withAppBasePath(
  publicUrl: string,
  basePath = process.env.NEXT_PUBLIC_APP_BASE_PATH ?? "",
): string {
  if (!publicUrl.startsWith("/") || publicUrl.startsWith("//")) return publicUrl;
  const normalized = normalizedBasePath(basePath);
  if (!normalized || publicUrl === normalized || publicUrl.startsWith(`${normalized}/`)) {
    return publicUrl;
  }
  return `${normalized}${publicUrl}`;
}
