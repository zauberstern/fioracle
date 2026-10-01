import { defineConfig } from "vite";

const pagesBase = process.env.PAGES_BASE || "/";

export default defineConfig({
  base: pagesBase,
  server: {
    port: 5174,
  },
  build: {
    target: "es2022",
  },
});
