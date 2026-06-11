import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  images: {
    unoptimized: true
  },
  async headers() {
    return [
      {
        source: '/chat-embed',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: "frame-ancestors 'self' http://localhost:8080 http://127.0.0.1:8080 http://127.0.0.1:5500/ http://localhost:5500/",
          },
        ],
      },
    ];
  },
};

export default nextConfig;