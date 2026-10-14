import { describe, expect, it } from "vitest";
import { TileMap } from "./TileMap";
import { buildStillmoor } from "./TownLayout";

describe("Stillmoor TileMap", () => {
  it("has solid outer walls", () => {
    const map = new TileMap();
    expect(map.isSolid(0, 0)).toBe(true);
    expect(map.isSolid(31, 23)).toBe(true);
    expect(map.wallSolidCount()).toBeGreaterThan(50);
  });

  it("has eight districts and five episode stones", () => {
    const map = new TileMap();
    expect(map.districtCount()).toBe(8);
    expect(map.stoneCount()).toBe(5);
  });

  it("places a sundial cell", () => {
    const layout = buildStillmoor();
    const { tx, ty } = layout.sundial;
    expect(layout.cells[ty][tx]).toBe("sundial");
  });

  it("keeps closed shops solid", () => {
    const layout = buildStillmoor();
    expect(layout.solid[layout.bard.ty][layout.bard.tx]).toBe(true);
    expect(layout.solid[layout.nameshop.ty][layout.nameshop.tx]).toBe(true);
  });

  it("dresses open grass with townsfolk and props", () => {
    const layout = buildStillmoor();
    expect(layout.scenery.length).toBeGreaterThanOrEqual(24);
    const frames = new Set(layout.scenery.map((s) => s.frame));
    expect([...frames].some((f) => f.startsWith("folk_"))).toBe(true);
    expect([...frames].some((f) => f.startsWith("prop_"))).toBe(true);
    for (const s of layout.scenery) {
      expect(layout.cells[s.ty][s.tx]).toBe("grass");
      expect(layout.solid[s.ty][s.tx]).toBe(true);
    }
  });
});
