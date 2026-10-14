/** Stillmoor stone/brass UI + Okabe-Ito P&L. Amber is heat rim / pins only. */

export const PALETTE = {
  bg: "#3A342C",
  stone0: "#3A342C",
  stone1: "#5C5346",
  stone2: "#8A7F6C",
  brass: "#B08D4F",
  parchment: "#D8C9A8",
  ink: "#2A241C",
  bone: "#E8E4D9",
  amber: "#E69F00",
  vermilion: "#D55E00",
  blueUp: "#0072B2",
  panel: "#5C5346",
  panelBorder: "#B08D4F",
  muted: "#8A7F6C",
  okabe: [
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#F0E442",
    "#D55E00",
    "#999999",
  ],
} as const;

/** Phase 2 weekly reading (paper page). */
export const READING = {
  page: "#F6F5F1",
  ink: "#171A20",
  signal: "#0072B2",
  warnShape: "#C2410C",
  inkBody: "#393C41",
  inkMute: "#5C5E62",
  hairline: "#D0D1D2",
} as const;

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16) || 0,
    parseInt(h.slice(2, 4), 16) || 0,
    parseInt(h.slice(4, 6), 16) || 0,
  ];
}
