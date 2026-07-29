import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * QianKun 前端 Vite 配置。
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    // 生产默认关闭 sourcemap, 需要排查时设 VITE_SOURCEMAP=true
    sourcemap: process.env.VITE_SOURCEMAP === "true",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@tanstack")) return "vendor-query";
          if (id.includes("@radix-ui")) return "vendor-radix";
          if (id.includes("axios")) return "vendor-http";
          if (id.includes("lucide-react")) return "vendor-icons";
          if (
            id.includes("react-dom") ||
            id.includes("react-router") ||
            id.includes("scheduler") ||
            /[/\\]react[/\\]/.test(id)
          ) {
            return "vendor-react";
          }
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
