import { describe, expect, it } from "vitest";
import { dailyReturnFromRow, lpplsCrashWindow, TapePlayer } from "./TapePlayer";

describe("TapePlayer.advance", () => {
  it("moves the index by one; debrief parent equals the posted tip", () => {
    const player = Object.create(TapePlayer.prototype) as TapePlayer & {
      frames: Array<{ asOf: string; byAsset: Record<string, unknown> }>;
      index: number;
      loaded: boolean;
      source: string;
    };
    player.frames = [
      { asOf: "2008-01-02", byAsset: {} },
      { asOf: "2008-01-03", byAsset: {} },
      { asOf: "2008-01-04", byAsset: {} },
    ];
    player.index = 0;
    player.loaded = true;
    player.source = "static";

    const postedBeforeAdvance = player.currentAsOf();
    expect(player.advance()).toBe(true);
    // After stamp, tape is already advanced; debrief continues that tip.
    const debriefParent = player.currentAsOf();
    expect(debriefParent).toBe("2008-01-03");
    expect(debriefParent).not.toBe(player.peekNextAsOf());
    expect(debriefParent).not.toBe(postedBeforeAdvance);
    expect(player.currentIndex).toBe(1);
  });
});

describe("sleeveDailyReturn helpers", () => {
  it("reads daily_return from the current row even at index 0", () => {
    expect(
      dailyReturnFromRow({ daily_return: 0.0123, as_of: "2008-01-02" })
    ).toBeCloseTo(0.0123);
  });

  it("returns NaN when the row is missing (no print)", () => {
    expect(Number.isNaN(dailyReturnFromRow(undefined))).toBe(true);
  });

  it("returns NaN when daily_return is null", () => {
    expect(
      Number.isNaN(dailyReturnFromRow({ daily_return: null, as_of: "2026-10-02" }))
    ).toBe(true);
  });
});

describe("lpplsCrashWindow", () => {
  it("stays closed when unavailable or empty", () => {
    expect(lpplsCrashWindow({ unavailable: true, tc_estimate: "2024-01-01" })).toBe(
      "-"
    );
    expect(lpplsCrashWindow({})).toBe("-");
  });

  it("formats a posted window when available", () => {
    expect(
      lpplsCrashWindow({
        unavailable: false,
        crash_window_start: "2020-03-01",
        crash_window_end: "2020-03-31",
      })
    ).toBe("2020-03-01..2020-03-31");
  });
});
