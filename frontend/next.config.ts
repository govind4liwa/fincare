import type { NextConfig } from "next";

// In Docker the frontend reaches the backend over the compose network (web:8000);
// override via BACKEND_INTERNAL_URL for local/other setups.
const backend = process.env.BACKEND_INTERNAL_URL ?? "http://web:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    // Proxy the DRF API so the browser stays same-origin (no CORS needed).
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
};

export default nextConfig;
