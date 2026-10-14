import { describe, expect, it } from "vitest";
import { readPin } from "./readPin";

describe("readPin", () => {
  it("keeps a known book and an ISO date", () => {
    const pin = readPin(
      "#/?book=BBG_EURO_AGG_CHF_HEDGED_TOTAL_RETURN&asof=2008-09-15",
    );
    expect(pin.book).toBe("BBG_EURO_AGG_CHF_HEDGED_TOTAL_RETURN");
    expect(pin.asof).toBe("2008-09-15");
  });

  it("drops an unknown book and a bad date", () => {
    const pin = readPin("#/?book=EURUSD&asof=September");
    expect(pin.book).toBeNull();
    expect(pin.asof).toBeNull();
  });
});
