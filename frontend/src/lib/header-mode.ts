export type AppHeaderMode = "admin" | "child" | "parent";

export function resolveAppHeaderMode({
  pathname,
  authenticated,
  systemAdmin,
  childMode,
}: {
  pathname: string;
  authenticated: boolean;
  systemAdmin: boolean;
  childMode: boolean;
}): AppHeaderMode {
  if (authenticated && systemAdmin && pathname.startsWith("/admin")) {
    return "admin";
  }
  if (authenticated && childMode) {
    return "child";
  }
  return "parent";
}
