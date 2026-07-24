/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy /api al backend en desarrollo
  async rewrites() {
    return [
      {
        source: "/api/proxy/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

