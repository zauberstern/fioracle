import type { TileMap } from "./TileMap";

export type Facing = "n" | "s" | "e" | "w";

const HOP_MS = 280;

export class Player {
  tx: number;
  ty: number;
  facing: Facing = "s";
  /** Advances only on a successful tile move. */
  stepIndex = 0;
  private hopUntil = 0;
  private hopDx = 0;
  private hopDy = 0;

  constructor(tx: number, ty: number) {
    this.tx = tx;
    this.ty = ty;
  }

  /** True when the hop tween has finished (next cardinal step allowed). */
  readyToHop(): boolean {
    return performance.now() >= this.hopUntil;
  }

  /** Hop deadline. A blocked step must leave this unchanged. */
  hopDeadline(): number {
    return this.hopUntil;
  }

  /**
   * Tile position the camera should follow. At the start of a hop this is the
   * tile we left; it eases onto tx/ty so the town does not jump under the sprite.
   */
  visualTile(): { x: number; y: number } {
    if (performance.now() >= this.hopUntil) return { x: this.tx, y: this.ty };
    const t = 1 - Math.max(0, this.hopUntil - performance.now()) / HOP_MS;
    return {
      x: this.tx + this.hopDx * (1 - t),
      y: this.ty + this.hopDy * (1 - t),
    };
  }

  tryMove(map: TileMap, dx: number, dy: number): boolean {
    if (dx === 0 && dy === 0) return false;
    if (Math.abs(dx) + Math.abs(dy) !== 1) return false;
    const nx = this.tx + dx;
    const ny = this.ty + dy;
    if (map.isSolid(nx, ny)) return false;
    if (dy < 0) this.facing = "n";
    else if (dy > 0) this.facing = "s";
    else if (dx < 0) this.facing = "w";
    else this.facing = "e";
    this.tx = nx;
    this.ty = ny;
    this.stepIndex += 1;
    this.hopDx = -dx;
    this.hopDy = -dy;
    this.hopUntil = performance.now() + HOP_MS;
    return true;
  }

  adjacentTo(tx: number, ty: number): boolean {
    return Math.abs(this.tx - tx) + Math.abs(this.ty - ty) <= 1;
  }

  spriteFrame(): string {
    const base = `player_${this.facing}`;
    const hopping = performance.now() < this.hopUntil;
    if (hopping && this.stepIndex % 2 === 1) {
      return `${base}_1`;
    }
    return base;
  }

  /** Pixel offset inside the tile during the hop; snap when reduced motion. */
  drawOffset(tilePx: number, reducedMotion: boolean): { x: number; y: number } {
    if (reducedMotion || performance.now() >= this.hopUntil) {
      return { x: 0, y: 0 };
    }
    const left = Math.max(0, this.hopUntil - performance.now()) / HOP_MS;
    return {
      x: this.hopDx * tilePx * left,
      y: this.hopDy * tilePx * left,
    };
  }
}
