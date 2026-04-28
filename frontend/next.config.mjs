/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Railway部署：使用环境变量BACKEND_URL，否则默认localhost
    // Railway内部网络：http://<service-name>.railway.internal:<port>
    const backendUrl = process.env.BACKEND_URL || process.env.RAILWAY_SERVICE_BACKEND_URL || "http://localhost:8000";
    console.log("[Next.js] Backend URL:", backendUrl);
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  experimental: {
    proxyTimeout: 1200000,
  },
};

export default nextConfig;
