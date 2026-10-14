import { useMarketStore } from "../../store/marketStore";
import { plainDate } from "../../../../shared/plainDate";
import { ScoreChart } from "./ScoreChart";

export function ReplayControls() {
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const history = useMarketStore((s) => s.scoreHistory);
  const tip = history[history.length - 1]?.time ?? null;
  const value = replayTimestamp ?? tip;
  const iso =
    value != null ? new Date(value * 1000).toISOString().slice(0, 10) : "";

  return (
    <div className="replay-controls">
      <p className="replay-meta">
        {iso ? `Pinned date ${plainDate(iso)}` : "The series are still loading."}
      </p>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ScoreChart />
      </div>
    </div>
  );
}
