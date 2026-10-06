/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  build: {
    target: process.env.TAURI_ENV_PLATFORM == "windows" ? "chrome105" : "safari13",
    minify: !process.env.TAURI_ENV_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
  test: {
    globals: true,
    environment: "jsdom",
    // Playwright owns *.spec.ts; vitest owns *.test.tsx. Keeping the globs
    // disjoint stops each runner from loading the other's fixtures and hooks.
    include: ["tests/**/*.test.{ts,tsx}"],
    exclude: ["tests/**/*.spec.ts", "node_modules/**", "dist/**"],
  },
});
