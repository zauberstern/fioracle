import { describe, expect, it } from "vitest";
import { shortestPath, type Tile } from "./pathfind";

function gridSolid(
  walls: Array<[number, number]>,
  w: number,
  h: number
): (tx: number, ty: number) => boolean {
  const set = new Set(walls.map(([x, y]) => `${x},${y}`));
  return (tx, ty) => {
    if (tx < 0 || ty < 0 || tx >= w || ty >= h) return true;
    return set.has(`${tx},${ty}`);
  };
}

describe("shortestPath", () => {
  it("open 5x5 from (0,0) to (2,0)", () => {
    const isSolid = gridSolid([], 5, 5);
    expect(shortestPath(isSolid, { tx: 0, ty: 0 }, { tx: 2, ty: 0 }, 5, 5)).toEqual([
      { tx: 1, ty: 0 },
      { tx: 2, ty: 0 },
    ]);
  });

  it("detours around a solid wall and never steps on it", () => {
    const isSolid = gridSolid([[1, 0]], 5, 5);
    const path = shortestPath(isSolid, { tx: 0, ty: 0 }, { tx: 2, ty: 0 }, 5, 5);
    expect(path).not.toBeNull();
    expect(path!.some((t) => t.tx === 1 && t.ty === 0)).toBe(false);
    expect(path![path!.length - 1]).toEqual({ tx: 2, ty: 0 });
  });

  it("returns null when the target is sealed", () => {
    // Room at (2,2) sealed by walls on all four neighbors + target itself walkable
    // Seal (4,4) by surrounding walls and leave no corridor.
    const walls: Array<[number, number]> = [
      [3, 3],
      [3, 4],
      [4, 3],
    ];
    // Make (4,4) unreachable from (0,0) by walling the corner approach.
    for (let x = 0; x < 5; x++) walls.push([x, 2]);
    for (let y = 3; y < 5; y++) walls.push([2, y]);
    const isSolid = gridSolid(walls, 5, 5);
    expect(shortestPath(isSolid, { tx: 0, ty: 0 }, { tx: 4, ty: 4 }, 5, 5)).toBeNull();
  });

  it("returns empty path when already at the target", () => {
    const isSolid = gridSolid([], 5, 5);
    const from: Tile = { tx: 1, ty: 1 };
    expect(shortestPath(isSolid, from, from, 5, 5)).toEqual([]);
  });

  it("returns null when the target itself is solid", () => {
    const isSolid = gridSolid([[2, 2]], 5, 5);
    expect(
      shortestPath(isSolid, { tx: 0, ty: 0 }, { tx: 2, ty: 2 }, 5, 5)
    ).toBeNull();
  });
});
