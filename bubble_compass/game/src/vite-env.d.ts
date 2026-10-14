/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_HISTORY_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.frag?raw" {
  const content: string;
  export default content;
}
