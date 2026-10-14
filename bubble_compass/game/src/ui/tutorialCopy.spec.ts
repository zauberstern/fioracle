import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { RULES, STAND_IN } from "./tutorialCopy";

const here = dirname(fileURLToPath(import.meta.url));

describe("tutorialCopy", () => {
  it("has four rules", () => {
    expect(RULES.length).toBe(4);
  });

  it("avoids em dashes and the strongest AI tells", () => {
    const all = [STAND_IN, ...RULES];
    for (const s of all) {
      expect(s).not.toMatch(/\u2014/);
      expect(s.toLowerCase()).not.toMatch(/let that sink/);
      expect(s.toLowerCase()).not.toMatch(/it's not/);
      expect(s.toLowerCase()).not.toMatch(/not just/);
    }
  });

  it("states the stamp and the score", () => {
    expect(STAND_IN).toBe(
      "The books start at equal weight. Change a weight, then stamp the sundial. A stamp scores that day only when every book and the bench have a print. A missing print does not score."
    );
    expect(RULES[1]).toBe("Right-click a tile for Stamp, Examine, Rules, or Cancel.");
    expect(RULES[3]).toBe(
      "Stamp the sundial to score the day. If that day has no print, the stamp does not score."
    );
  });

  it("does not import ScoreKeeper", () => {
    const src = readFileSync(join(here, "tutorialCopy.ts"), "utf8");
    expect(src).not.toMatch(/ScoreKeeper/);
  });
});
