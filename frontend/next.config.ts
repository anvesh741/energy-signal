import type { NextConfig } from "next";

// STATIC_EXPORT=1 builds a server-less site that reads JSON snapshots from public/data
// (written by `python -m app.export_static`); used for GitHub Pages.
const isStatic = process.env.STATIC_EXPORT === "1";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = isStatic
  ? {
      output: "export",
      basePath,
      trailingSlash: true,
      images: { unoptimized: true },
      env: { NEXT_PUBLIC_STATIC: "1", NEXT_PUBLIC_BASE_PATH: basePath },
    }
  : {
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: "http://127.0.0.1:8000/api/:path*",
          },
        ];
      },
    };

export default nextConfig;
