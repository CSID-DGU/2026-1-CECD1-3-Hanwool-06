import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// 단일 HTML 산출 전용 빌드 설정 (팀원 공유용).
// 사용: npx vite build --config vite.singlefile.config.js
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: { outDir: "dist-single" },
});
