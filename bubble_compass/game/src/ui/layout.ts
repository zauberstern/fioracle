/** Stillmoor 960x540 pixel lock. Origin top-left. */

export const CANVAS = { w: 960, h: 540 } as const;

export const VIEWPORT = { x: 0, y: 0, w: 712, h: 334 } as const;
/** Inner height is exactly 10 * TILE_DRAW so the last row is not a 6px strip. */
export const VIEWPORT_INNER = { x: 4, y: 4, w: 704, h: 320 } as const;

export const MINIMAP = { x: 600, y: 8, w: 104, h: 104 } as const;

export const PACK = { x: 712, y: 0, w: 248, h: 334 } as const;
export const SLOT_ORIGIN = { x: 720, y: 36 } as const;
export const SLOT = { w: 36, h: 28, gap: 4 } as const;
export const SLOT_PITCH = { x: 40, y: 32 } as const;

export const CHAT = { x: 0, y: 328, w: 712, h: 212 } as const;

export const ORB_CLUSTER = { x: 712, y: 334, w: 248, h: 206 } as const;
export const STAMP = { x: 744, y: 430, w: 184, h: 48 } as const;

export const TILE_SRC = 16;
export const TILE_DRAW = 32;
export const MAP_W = 32;
export const MAP_H = 24;

export function slotRect(i: number): { x: number; y: number; w: number; h: number } {
  return {
    x: SLOT_ORIGIN.x + (i % 4) * SLOT_PITCH.x,
    y: SLOT_ORIGIN.y + Math.floor(i / 4) * SLOT_PITCH.y,
    w: SLOT.w,
    h: SLOT.h,
  };
}

export function hitTest(
  mx: number,
  my: number,
  r: { x: number; y: number; w: number; h: number }
): boolean {
  return mx >= r.x && mx < r.x + r.w && my >= r.y && my < r.y + r.h;
}
