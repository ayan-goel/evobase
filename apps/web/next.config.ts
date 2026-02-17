import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produce a self-contained Node.js server for Docker deployments.
  // The output lives in .next/standalone and includes only the files needed
  // to run the app (no dev dependencies, no source maps).
  output: "standalone",
};

export default nextConfig;
