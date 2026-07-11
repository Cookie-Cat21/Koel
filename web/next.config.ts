import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for web/Dockerfile standalone runner (compose profile `web`).
  output: "standalone",
};

export default nextConfig;
