import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// dev server proxies API calls to the FastAPI process on 8420,
// so `npm run dev` (hot reload) and the built app behave identically.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8420",
      "/health": "http://localhost:8420",
    },
  },
});
