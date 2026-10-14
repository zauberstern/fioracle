import type { KAPLAYCtx } from "kaplay";
import { MINIMAP } from "./layout";
import type { TileMap } from "../world/TileMap";
import type { Player } from "../world/Player";
import { MAP_H, MAP_W } from "./layout";
import { TYPE } from "./type";

/** Heat weather glyph: empty / half-hatch / chevrons. */
export function heatGlyph(heat: number): "empty" | "half" | "chevron" {
  if (heat >= 70) return "chevron";
  if (heat >= 40) return "half";
  return "empty";
}

export function drawMinimap(
  k: KAPLAYCtx,
  map: TileMap,
  player: Player,
  heat: number,
  atlasOk: boolean
): void {
  const { x, y, w, h } = MINIMAP;
  k.drawCircle({
    pos: k.vec2(x + w / 2, y + h / 2),
    radius: w / 2 - 2,
    color: k.rgb(58, 52, 44),
  });
  if (atlasOk) {
    try {
      k.drawSprite({
        sprite: "orb_ring",
        pos: k.vec2(x, y),
        width: w,
        height: h,
      });
    } catch {
      k.drawCircle({
        pos: k.vec2(x + w / 2, y + h / 2),
        radius: w / 2 - 2,
        fill: false,
        outline: { width: 3, color: k.rgb(176, 141, 79) },
      });
    }
  } else {
    k.drawCircle({
      pos: k.vec2(x + w / 2, y + h / 2),
      radius: w / 2 - 2,
      fill: false,
      outline: { width: 3, color: k.rgb(176, 141, 79) },
    });
  }

  const cx = x + w / 2;
  const cy = y + h / 2;
  const radius = w / 2 - 2;
  const ox = x + 12;
  const oy = y + 12;
  const iw = w - 24;
  const ih = h - 24;
  const inOrb = (px: number, py: number) => {
    const dx = px - cx;
    const dy = py - cy;
    return dx * dx + dy * dy <= radius * radius;
  };
  for (const s of map.layout.stones) {
    const px = ox + (s.tx / MAP_W) * iw;
    const py = oy + (s.ty / MAP_H) * ih;
    if (!inOrb(px, py)) continue;
    k.drawRect({
      pos: k.vec2(px - 2, py - 2),
      width: 4,
      height: 4,
      color: k.rgb(230, 159, 0),
    });
  }
  const ppx = ox + (player.tx / MAP_W) * iw;
  const ppy = oy + (player.ty / MAP_H) * ih;
  if (inOrb(ppx, ppy)) {
    k.drawCircle({
      pos: k.vec2(ppx, ppy),
      radius: 3,
      color: k.rgb(232, 228, 217),
    });
  }

  const glyph = heatGlyph(heat);
  const gx = x + w / 2;
  const gy = y + h - 14;
  if (glyph === "empty") {
    k.drawCircle({
      pos: k.vec2(gx, gy),
      radius: 8,
      fill: false,
      outline: { width: 2, color: k.rgb(176, 141, 79) },
    });
  } else if (glyph === "half") {
    k.drawCircle({
      pos: k.vec2(gx, gy),
      radius: 8,
      fill: false,
      outline: { width: 2, color: k.rgb(230, 159, 0) },
    });
    k.drawRect({
      pos: k.vec2(gx - 6, gy - 1),
      width: 12,
      height: 2,
      color: k.rgb(230, 159, 0),
    });
  } else {
    for (let i = 0; i < 3; i++) {
      k.drawRect({
        pos: k.vec2(gx - 6 + i * 2, gy - 6 + i * 3),
        width: 12 - i * 2,
        height: 2,
        color: k.rgb(230, 159, 0),
      });
    }
  }
  k.drawText({
    text: `${Math.round(heat)}`,
    pos: k.vec2(gx + 14, gy - 6),
    font: TYPE.hud.font,
    size: TYPE.hud.size,
    color: k.rgb(232, 228, 217),
  });
}

/** Map a screen click inside the minimap circle to a tile, or null. */
export function minimapTileAt(
  mx: number,
  my: number
): { tx: number; ty: number } | null {
  const { x, y, w, h } = MINIMAP;
  const cx = x + w / 2;
  const cy = y + h / 2;
  const radius = w / 2 - 2;
  const dx = mx - cx;
  const dy = my - cy;
  if (dx * dx + dy * dy > radius * radius) return null;
  const ox = x + 12;
  const oy = y + 12;
  const iw = w - 24;
  const ih = h - 24;
  if (iw <= 0 || ih <= 0) return null;
  const tx = Math.max(0, Math.min(MAP_W - 1, Math.floor(((mx - ox) / iw) * MAP_W)));
  const ty = Math.max(0, Math.min(MAP_H - 1, Math.floor(((my - oy) / ih) * MAP_H)));
  return { tx, ty };
}
