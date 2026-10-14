/** Canvas type scale for Kaplay drawText (loaded via manifest PlexSans/PlexMono). */

type MeasureHost = {
  formatText?: (opt: {
    text: string;
    size: number;
    font?: string;
    width?: number;
  }) => { height?: number };
};

/** Height of a wrapped label. Prefers Kaplay, then canvas measure, then one spare row. */
export function textBlockHeight(
  k: MeasureHost,
  text: string,
  font: string,
  size: number,
  width: number
): number {
  try {
    const measured = k.formatText?.({ text, font, size, width });
    if (measured && typeof measured.height === "number" && measured.height > 0) {
      return measured.height + 4;
    }
  } catch {
    /* font missing or still pending */
  }
  const rows = canvasRows(text, font, size, width);
  return Math.max(22, rows * 22);
}

function canvasRows(text: string, font: string, size: number, width: number): number {
  if (typeof document === "undefined" || width <= 0) {
    const per = Math.max(8, Math.floor(width / (size * 0.55)));
    return Math.max(1, Math.ceil(text.length / Math.max(1, per))) + 1;
  }
  const ctx = document.createElement("canvas").getContext("2d");
  if (!ctx) return Math.max(1, Math.ceil(text.length / 24)) + 1;
  const family = font === "PlexMono" ? "IBM Plex Mono" : "IBM Plex Sans";
  ctx.font = `${size}px "${family}", sans-serif`;
  const words = text.split(/\s+/).filter(Boolean);
  let rows = 1;
  let line = "";
  for (const word of words) {
    const trial = line ? `${line} ${word}` : word;
    if (ctx.measureText(trial).width > width && line) {
      rows += 1;
      line = word;
    } else {
      line = trial;
    }
  }
  return rows + 1;
}

export const TYPE = {
  chat: { font: "PlexSans", size: 18 },
  mouse: { font: "PlexSans", size: 18 },
  hud: { font: "PlexMono", size: 16 },
  title: { font: "PlexSans", size: 24 },
  stamp: { font: "PlexSans", size: 18 },
} as const;
