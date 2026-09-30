import { DateTime } from "luxon";
import { useMarketStore } from "../../store/marketStore";
import { Hint } from "../ui/Hint";

export function TopBar() {
  const asset = useMarketStore((s) => s.currentAsset);
  const connected = useMarketStore((s) => s.connected);
  const replayMode = useMarketStore((s) => s.replayMode);
  const timestamp = useMarketStore((s) => s.lastUpdate);

  const display = DateTime.fromISO(timestamp, { zone: "utc" })
    .setZone("America/New_York")
    .toFormat("dd LLL yyyy HH:mm ZZZZ");

  const utc = DateTime.fromISO(timestamp, { zone: "utc" }).toFormat("HH:mm");

  const statusEntry = replayMode ? "scrubbing" : connected ? "live" : "offline";
  const statusClass = replayMode ? "replay" : connected ? "live" : "offline";
  const statusLabel = replayMode ? "Scrubbing" : connected ? "Live" : "Offline";

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <span className="app-name">Bubble Compass</span>
        <span className="asset-name">{asset}</span>
      </div>
      <div className="top-bar-center">
        <Hint entry="asOf">
          <span className="timestamp">
            As of {display} · UTC {utc}
          </span>
        </Hint>
      </div>
      <div className="top-bar-right">
        <Hint entry={statusEntry}>
          <span className={`status-pill ${statusClass}`}>{statusLabel}</span>
        </Hint>
      </div>
    </header>
  );
}
