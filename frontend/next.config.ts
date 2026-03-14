import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/v1/ws/:path*",
        destination: `${backendUrl}/api/v1/ws/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
