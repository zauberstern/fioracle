import * as Slider from "@radix-ui/react-slider";
import { DateTime } from "luxon";
import { useMarketStore } from "../../store/marketStore";
import { Hint } from "../ui/Hint";
import { ScoreChart } from "./ScoreChart";

export function ReplayControls() {
  const history = useMarketStore((s) => s.scoreHistory);
  const replayMode = useMarketStore((s) => s.replayMode);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const setReplayMode = useMarketStore((s) => s.setReplayMode);
  const setReplayTimestamp = useMarketStore((s) => s.setReplayTimestamp);

  const min = history[0]?.time ?? 0;
  const max = history[history.length - 1]?.time ?? 1;
  const value = replayTimestamp ?? max;

  const label = DateTime.fromSeconds(value, { zone: "utc" })
    .setZone("America/New_York")
    .toFormat("dd LLL yyyy HH:mm ZZZZ");

  return (
    <div className="replay-controls">
      <div className="replay-row">
        <Hint entry="scrubHistory">
          <button
            type="button"
            className="replay-button"
            data-active={replayMode ? "true" : "false"}
            onClick={() => setReplayMode(!replayMode)}
          >
            {replayMode ? "Stop scrubbing" : "Scrub history"}
          </button>
        </Hint>
        <Hint entry="asOf">
          <span className="replay-meta">{label}</span>
        </Hint>
      </div>
      <Slider.Root
        className="replay-slider-root"
        value={[value]}
        min={min}
        max={max}
        step={86400}
        aria-label="History date"
        aria-valuetext={label}
        onValueChange={(vals) => setReplayTimestamp(vals[0] ?? max)}
      >
        <Slider.Track className="replay-slider-track">
          <Slider.Range className="replay-slider-range" />
        </Slider.Track>
        <Slider.Thumb className="replay-slider-thumb" />
      </Slider.Root>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ScoreChart />
      </div>
    </div>
  );
}
