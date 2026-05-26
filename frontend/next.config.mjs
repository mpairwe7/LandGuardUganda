/** @type {import('next').NextConfig} */
// /api/proxy/* is served by a runtime route handler at
// src/app/api/proxy/[...path]/route.ts so BACKEND_URL is honoured at
// request time, not at `next build` time. The previous rewrites()-based
// approach baked the (CI-time-empty) BACKEND_URL into the standalone
// bundle.
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  experimental: {
    typedRoutes: true,
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self)" },
        ],
      },
    ];
  },
};

export default nextConfig;
