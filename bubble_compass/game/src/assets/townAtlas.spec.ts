import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { TOWN_FRAMES } from "./manifest";
import atlas from "../../public/atlases/town.kaplay.json";

describe("town atlas frames", () => {
  it("TOWN_FRAMES keys match public/atlases/town.kaplay.json", () => {
    const atlasKeys = Object.keys(atlas).sort();
    const named = [...TOWN_FRAMES].sort();
    expect(atlasKeys).toEqual(named);
    expect(named).toContain("fx_spark");
    expect(named).toContain("fx_star");
  });

  it("ships a transparent column, not a solid wall panel", () => {
    const out = execFileSync(
      "python3",
      [
        "-c",
        "import json; from PIL import Image; from pathlib import Path; root=Path('public/atlases'); meta=json.loads((root/'town.kaplay.json').read_text()); im=Image.open(root/'town.png').convert('RGBA'); box=meta['prop_column']; c=im.crop((box['x'],box['y'],box['x']+box['width'],box['y']+box['height'])); n=sum(1 for p in c.getdata() if p[3]<16); print(n)",
      ],
      { encoding: "utf8" }
    );
    expect(Number(out.trim())).toBeGreaterThan(20);
  });
});
