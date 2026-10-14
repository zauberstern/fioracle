import { describe, expect, it, vi } from "vitest";
import { JuiceBus } from "./JuiceBus";

describe("JuiceBus", () => {
  it("negativePrint skips shake when reduced motion is on", () => {
    const juice = new JuiceBus();
    const shake = vi.fn();
    const flash = vi.fn();
    juice.bind(
      {
        shake,
        flash,
        rgb: (r: number, g: number, b: number) => ({ r, g, b }),
        wait: () => undefined,
      },
      { play: vi.fn() } as never
    );
    juice.setReducedMotion(true);
    juice.negativePrint();
    expect(shake).not.toHaveBeenCalled();
  });

  it("stamp does not full-screen flash", () => {
    const juice = new JuiceBus();
    const flash = vi.fn();
    juice.bind(
      {
        shake: vi.fn(),
        flash,
        rgb: (r: number, g: number, b: number) => ({ r, g, b }),
        wait: () => undefined,
      },
      { play: vi.fn() } as never
    );
    juice.setReducedMotion(false);
    juice.stamp();
    expect(flash).not.toHaveBeenCalled();
  });
});
