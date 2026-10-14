import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { TYPE } from "./type";

const here = dirname(fileURLToPath(import.meta.url));

describe("TYPE", () => {
  it("locks readable Plex sizes", () => {
    expect(TYPE.chat.size).toBe(18);
    expect(TYPE.chat.font).toBe("PlexSans");
    expect(TYPE.hud.font).toBe("PlexMono");
    expect(TYPE.hud.size).toBe(16);
    expect(TYPE.title.size).toBe(24);
  });

  it("AsOfDeskScene drawText uses font and never 11/12px", () => {
    const src = readFileSync(join(here, "../scenes/AsOfDeskScene.ts"), "utf8");
    expect(src).not.toMatch(/size:\s*11\b/);
    expect(src).not.toMatch(/size:\s*12\b/);
    const blocks = src.match(/k\.drawText\(\{[\s\S]*?\}\)/g) ?? [];
    expect(blocks.length).toBeGreaterThan(0);
    for (const block of blocks) {
      expect(block).toMatch(/font:/);
    }
  });

  it("AsOfDeskScene paints cells and does not markArtMissing", () => {
    const src = readFileSync(join(here, "../scenes/AsOfDeskScene.ts"), "utf8");
    expect(src).toMatch(/paintCell\(/);
    expect(src).toMatch(/chat\.markArtMissing\(\)/);
    expect(src).not.toMatch(/text:\s*"art missing"/);
    expect(src).not.toMatch(/rgb\(255,\s*255,\s*0\)/);
  });

  it("title, debrief, and crash avoid yellow and empty-tape orange", () => {
    for (const file of ["TitleScene.ts", "DebriefScene.ts", "CrashScene.ts"]) {
      const src = readFileSync(join(here, "../scenes", file), "utf8");
      expect(src).not.toMatch(/rgb\(255,\s*255,\s*0\)/);
      expect(src).not.toMatch(/rgb\(213,\s*94,\s*0\)/);
    }
  });
});
