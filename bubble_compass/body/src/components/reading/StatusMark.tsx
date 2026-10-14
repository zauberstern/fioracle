import type { StatusWord } from "../../narrator/heat";

type Word = StatusWord | "Loading";

export function StatusMark({ word }: { word: Word }) {
  if (word === "Loading") return null;
  const cls = `status-mark status-mark-${word.toLowerCase()}`;
  return (
    <span className={cls} aria-hidden="true">
      <svg viewBox="0 0 32 32" width="32" height="32">
        <circle className="status-mark-face" cx="16" cy="16" r="11" />
        {word === "Quiet" ? (
          <>
            <path className="status-mark-eye" d="M10 14h3M19 14h3" />
            <path className="status-mark-mouth" d="M12 20h8" />
          </>
        ) : null}
        {word === "Warming" ? (
          <>
            <circle className="status-mark-eye" cx="12" cy="14" r="1.3" />
            <circle className="status-mark-eye" cx="20" cy="14" r="1.3" />
            <path className="status-mark-mouth" d="M12 20h8" />
          </>
        ) : null}
        {word === "Stretched" ? (
          <>
            <circle className="status-mark-eye" cx="12" cy="13" r="1.7" />
            <circle className="status-mark-eye" cx="20" cy="13" r="1.7" />
            <path className="status-mark-mouth" d="M12 22c2.2-2.4 5.6-2.4 8 0" />
          </>
        ) : null}
      </svg>
    </span>
  );
}
