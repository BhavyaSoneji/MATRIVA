import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  // Old per-feature pages now live inside the chat; keep bookmarks working.
  async redirects() {
    return ["dashboard", "nutrition", "ayurveda", "lifestyle", "guidance", "sources", "recommendations"].map(
      (page) => ({ source: `/${page}`, destination: "/chat", permanent: false })
    );
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
