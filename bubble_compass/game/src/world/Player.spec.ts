import { describe, expect, it } from "vitest";
import { Player } from "./Player";
import type { TileMap } from "./TileMap";

function solidMap(blocked: boolean): TileMap {
  return {
    isSolid: () => blocked,
  } as unknown as TileMap;
}

describe("Player.tryMove", () => {
  it("leaves facing and hop deadline alone when the tile is solid", () => {
    const player = new Player(4, 4);
    player.facing = "s";
    const before = player.hopDeadline();
    expect(player.tryMove(solidMap(true), 0, 1)).toBe(false);
    expect(player.facing).toBe("s");
    expect(player.tx).toBe(4);
    expect(player.ty).toBe(4);
    expect(player.hopDeadline()).toBe(before);
    expect(player.readyToHop()).toBe(true);
  });

  it("faces the free step and uses the walk frame on an odd hop", () => {
    const player = new Player(4, 4);
    expect(player.tryMove(solidMap(false), 0, 1)).toBe(true);
    expect(player.facing).toBe("s");
    expect(player.ty).toBe(5);
    expect(player.stepIndex).toBe(1);
    expect(player.spriteFrame()).toBe("player_s_1");
    expect(player.readyToHop()).toBe(false);
    const vis = player.visualTile();
    expect(vis.y).toBeLessThan(5);
    expect(vis.y).toBeGreaterThanOrEqual(4);
  });
});
