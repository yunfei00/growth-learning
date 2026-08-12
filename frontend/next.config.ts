import type { NextConfig } from "next";

const basePath = process.env.NEXT_PUBLIC_APP_BASE_PATH?.trim() ?? "";

if (basePath && (!basePath.startsWith("/") || basePath.endsWith("/"))) {
  throw new Error("NEXT_PUBLIC_APP_BASE_PATH must start with '/' and must not end with '/'.");
}

const nextConfig: NextConfig = {
  basePath,
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  experimental: {
    cpus: 1,
  },
};

export default nextConfig;
