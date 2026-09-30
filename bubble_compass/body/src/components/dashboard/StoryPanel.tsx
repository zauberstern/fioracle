import { DateTime } from "luxon";
import { useMarketStore } from "../../store/marketStore";
import { storyLead, stretchHeadline } from "../../copy/sensational";
import { glossary } from "../../copy/glossary";
import { EpisodePins } from "./EpisodePins";
import { HintLabel } from "../ui/Hint";

export function StoryPanel() {
  const asset = useMarketStore((s) => s.currentAsset);
  const score = useMarketStore((s) => s.bubbleScore);
  const state = useMarketStore((s) => s.getAssetState(asset));
  const lastUpdate = useMarketStore((s) => s.lastUpdate);
  const historySource = useMarketStore((s) => s.historySource);

  const asOf = DateTime.fromISO(lastUpdate, { zone: "utc" })
    .setZone("America/New_York")
    .toFormat("dd LLL yyyy");

  return (
    <section className="story-panel">
      <p className="panel-title">
        <HintLabel entry="story" />
      </p>
      <EpisodePins />
      <h3 className="story-lead">{storyLead(asset, score, state.regime.regimeState, asOf)}</h3>
      <ul className="story-bullets">
        <li>
          {stretchHeadline(
            state.bsadf.bubbleFlag,
            state.bsadf.bsadfStat,
            state.bsadf.criticalValue
          )}
        </li>
        <li>
          {glossary.crashTiming.label}: confidence{" "}
          {(state.lppls.lppConfidence * 100).toFixed(0)}%
        </li>
        <li>
          {glossary.newsTone.label}:{" "}
          {state.sentiment.unavailable
            ? "unavailable (no headline tape)"
            : `velocity ${state.sentiment.sentimentVelocity.toFixed(2)}`}
        </li>
        <li>
          Tape source: {historySource === "api" ? "history parquet" : historySource}
        </li>
      </ul>
    </section>
  );
}
