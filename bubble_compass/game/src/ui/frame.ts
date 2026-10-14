/** Outlined parchment/stone wells (no stretched 32px sprites). */

export type WellDraw = (o: {
  x: number;
  y: number;
  w: number;
  h: number;
  fill: [number, number, number];
  outline: [number, number, number];
  outlineWidth: number;
}) => void;

export function drawWell(
  drawRect: WellDraw,
  x: number,
  y: number,
  w: number,
  h: number,
  fill: [number, number, number],
  outline: [number, number, number]
): void {
  drawRect({
    x,
    y,
    w,
    h,
    fill,
    outline,
    outlineWidth: 3,
  });
}

export const WELL_PARCHMENT: [number, number, number] = [216, 201, 168];
export const WELL_STONE: [number, number, number] = [58, 52, 44];
export const WELL_BRASS: [number, number, number] = [176, 141, 79];
