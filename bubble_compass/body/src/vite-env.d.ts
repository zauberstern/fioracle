/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL: string;
  readonly VITE_API_URL?: string;
  readonly VITE_GAME_URL?: string;
  readonly VITE_HISTORY_BASE?: string;
  readonly VITE_ENABLE_WORLD_3D?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Min bundle only. No @types package; DiagnosticsView is the sole importer. */
declare module "plotly.js-dist-min" {
  interface PlotlyMin {
    react: (
      el: HTMLElement,
      data: unknown[],
      layout: unknown,
      config?: unknown
    ) => void;
  }
  const Plotly: PlotlyMin;
  export default Plotly;
}
