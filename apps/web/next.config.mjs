const API = process.env.API_INTERNAL_URL || 'http://localhost:8000';
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() { return [{ source: '/api/v1/:path*', destination: `${API}/api/v1/:path*` }]; },
  async headers() {
    return [{ source: '/:path*', headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' }, { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' } ] }];
  },
};
export default nextConfig;
