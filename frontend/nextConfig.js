/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001') + '/api/v1/:path*',
      },
      {
        source: '/health/:path*',
        destination: (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001') + '/health/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
