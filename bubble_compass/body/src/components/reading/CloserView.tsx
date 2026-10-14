import { BOOKS, bookName } from "../../../../shared/books";
import { plainDate } from "../../../../shared/plainDate";
import { EvidencePanel } from "../dashboard/EvidencePanel";
import { useMarketStore } from "../../store/marketStore";

export function CloserView() {
  const asset = useMarketStore((s) => s.currentAsset);
  const setCurrentAsset = useMarketStore((s) => s.setCurrentAsset);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const history = useMarketStore((s) => s.scoreHistory);
  const name = bookName(asset);
  const asDate = (time: number) =>
    plainDate(new Date(time * 1000).toISOString().slice(0, 10));
  const first = history[0];
  const last = history[history.length - 1];
  const pin =
    replayTimestamp != null ? asDate(replayTimestamp) : "";
  const span =
    first && last
      ? `from ${asDate(first.time)} through ${asDate(last.time)}`
      : "";

  return (
    <article className="reading-page closer-view">
      <header className="closer-head">
        <h1>Look closer</h1>
      </header>
      <p className="reading-lede">
        {span
          ? `Heat and the fast rise for ${name}, ${span}.${
              pin && last && pin !== asDate(last.time)
                ? ` The week page is pinned at ${pin}. The chart still draws every later row.`
                : ""
            }`
          : `Heat and the fast rise for ${name}. The history is still loading.`}
      </p>
      <label className="closer-book">
        Book
        <select
          value={asset}
          onChange={(e) => setCurrentAsset(e.target.value)}
        >
          {BOOKS.map((book) => (
            <option key={book.id} value={book.id}>
              {book.mark} {book.plain}
            </option>
          ))}
        </select>
      </label>
      <div className="closer-charts">
        <EvidencePanel fullSpan />
      </div>
    </article>
  );
}
