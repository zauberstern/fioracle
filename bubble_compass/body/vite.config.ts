import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const pagesBase = process.env.PAGES_BASE || "/";

export default defineConfig({
  base: pagesBase,
  plugins: [react()],
  server: {
    port: 5173,
    watch: { usePolling: true, interval: 1000 },
    // Serve Pages history JSON at /data for desk + dashboard offline DEV.
    fs: { allow: ["..", "../.."] },
  },
  publicDir: "public",
});
