import { describe, expect, it } from "vitest";
import { BOOKS } from "../../../shared/books";

describe("BOOKS display", () => {
  it("gives every book a plain name, a mark, a group, and a full-instrument hint", () => {
    expect(BOOKS).toHaveLength(23);
    for (const book of BOOKS) {
      expect(book.plain.length).toBeGreaterThan(2);
      expect(book.mark.length).toBeGreaterThan(0);
      expect(book.group.length).toBeGreaterThan(0);
      expect(book.hint).toMatch(/[A-Za-z]/);
      expect(book.hint).not.toMatch(/\u2014/);
    }
  });
});
