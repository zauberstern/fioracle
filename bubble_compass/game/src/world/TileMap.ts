import { MAP_H, MAP_W, TILE_DRAW, VIEWPORT_INNER } from "../ui/layout";
import type { StillmoorLayout } from "./TownLayout";
import { buildStillmoor } from "./TownLayout";

export class TileMap {
  readonly layout: StillmoorLayout;
  camX = 0;
  camY = 0;

  constructor(layout?: StillmoorLayout) {
    this.layout = layout ?? buildStillmoor();
  }

  isSolid(tx: number, ty: number): boolean {
    if (tx < 0 || ty < 0 || tx >= MAP_W || ty >= MAP_H) return true;
    return this.layout.solid[ty][tx];
  }

  clampCamera(playerTx: number, playerTy: number): void {
    const viewTilesX = Math.floor(VIEWPORT_INNER.w / TILE_DRAW);
    const viewTilesY = Math.floor(VIEWPORT_INNER.h / TILE_DRAW);
    const maxX = Math.max(0, MAP_W - viewTilesX);
    const maxY = Math.max(0, MAP_H - viewTilesY);
    this.camX = Math.max(0, Math.min(maxX, playerTx - Math.floor(viewTilesX / 2)));
    this.camY = Math.max(0, Math.min(maxY, playerTy - Math.floor(viewTilesY / 2)));
  }

  tileAtScreen(
    sx: number,
    sy: number
  ): { tx: number; ty: number } | null {
    const ix = sx - VIEWPORT_INNER.x;
    const iy = sy - VIEWPORT_INNER.y;
    if (ix < 0 || iy < 0 || ix >= VIEWPORT_INNER.w || iy >= VIEWPORT_INNER.h) {
      return null;
    }
    const tx = this.camX + Math.floor(ix / TILE_DRAW);
    const ty = this.camY + Math.floor(iy / TILE_DRAW);
    if (tx < 0 || ty < 0 || tx >= MAP_W || ty >= MAP_H) return null;
    return { tx, ty };
  }

  screenOf(tx: number, ty: number): { x: number; y: number } {
    return {
      x: VIEWPORT_INNER.x + (tx - this.camX) * TILE_DRAW,
      y: VIEWPORT_INNER.y + (ty - this.camY) * TILE_DRAW,
    };
  }

  districtCount(): number {
    return this.layout.districts.length;
  }

  stoneCount(): number {
    return this.layout.stones.length;
  }

  wallSolidCount(): number {
    let n = 0;
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        if (this.layout.cells[y][x] === "wall" && this.layout.solid[y][x]) n++;
      }
    }
    return n;
  }
}
