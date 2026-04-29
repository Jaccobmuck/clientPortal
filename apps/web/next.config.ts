import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Strict mode for catching issues early
  reactStrictMode: true,

  // All API calls go through Next.js → FastAPI
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
