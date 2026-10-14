import { beforeEach, describe, expect, it, vi } from "vitest";
import { StampAlbum, albumDebriefLine } from "./StampAlbum";

describe("StampAlbum", () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => {
        store.set(k, v);
      },
      clear: () => store.clear(),
      removeItem: (k: string) => {
        store.delete(k);
      },
    });
  });

  it("records real stamps and persists count", () => {
    const a = new StampAlbum();
    a.record({ asOf: "2008-09-15", score: 0.1, portReturn: -0.02 });
    a.record({ asOf: "2008-10-15", score: 0.2, portReturn: 0.01 });
    expect(a.count()).toBe(2);
    const b = new StampAlbum();
    expect(b.count()).toBe(2);
    expect(b.list()[0]?.asOf).toBe("2008-09-15");
  });

  it("debrief line only contains record()ed dates", () => {
    const a = new StampAlbum();
    a.record({ asOf: "2020-02-26", score: 0, portReturn: -0.01 });
    const line = albumDebriefLine(a.list());
    expect(line).toContain("26 Feb 2020");
    expect(line).not.toContain("2020-03-16");
    expect(line).toMatch(/print/);
  });
});
