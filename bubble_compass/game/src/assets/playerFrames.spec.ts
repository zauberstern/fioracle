import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";

describe("town walker atlas", () => {
  it("uses one body for every facing", () => {
    const out = execFileSync("python3", ["scripts/test_player_frames.py"], {
      encoding: "utf8",
    });
    expect(out).toMatch(/one body/);
  });
});
