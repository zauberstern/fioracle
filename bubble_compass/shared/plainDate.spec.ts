import { describe, expect, it } from "vitest";
import { plainDate } from "./plainDate";

describe("plainDate", () => {
  it("reads an ISO day as day month year", () => {
    expect(plainDate("2026-10-02")).toBe("2 Oct 2026");
    expect(plainDate("2020-03-26T00:00:00.000")).toBe("26 Mar 2020");
  });

  it("leaves a non-date alone", () => {
    expect(plainDate("—")).toBe("—");
    expect(plainDate("unknown")).toBe("unknown");
  });
});