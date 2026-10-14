import { BOOKS } from "../../../shared/books";

export function readPin(hash: string): { book: string | null; asof: string | null } {
  const query = hash.split("?")[1] || "";
  const params = new URLSearchParams(query);
  const book = params.get("book");
  const asof = params.get("asof");
  const known = book != null && BOOKS.some((item) => item.id === book);
  const dated = asof != null && /^\d{4}-\d{2}-\d{2}$/.test(asof);
  return {
    book: known ? book : null,
    asof: dated ? asof : null,
  };
}
