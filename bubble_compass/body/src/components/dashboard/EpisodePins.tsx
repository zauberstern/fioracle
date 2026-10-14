import { EPISODES } from "../../copy/episodes";
import { useMarketStore } from "../../store/marketStore";

export function EpisodePins() {
  const jumpToEpisode = useMarketStore((s) => s.jumpToEpisode);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);
  const historyLoaded = useMarketStore((s) => s.historyLoaded);
  const historySource = useMarketStore((s) => s.historySource);
  const pinsEnabled =
    historyLoaded && (historySource === "api" || historySource === "static");

  return (
    <div className="episode-pins" aria-label="Historical episodes">
      {EPISODES.map((ep) => {
        const active =
          pinsEnabled &&
          replayTimestamp != null &&
          Math.abs(
            replayTimestamp -
              Math.floor(Date.UTC(+ep.date.slice(0, 4), +ep.date.slice(5, 7) - 1, +ep.date.slice(8, 10)) / 1000)
          ) <
            86400 * 3;
        return (
          <button
            key={ep.id}
            type="button"
            className="episode-pin"
            data-active={active ? "true" : "false"}
            title={pinsEnabled ? ep.blurb : "Pins wait until the history loads"}
            disabled={!pinsEnabled}
            onClick={() => jumpToEpisode(ep.date)}
          >
            <span className="episode-pin-date">{ep.date.slice(0, 4)}</span>
            <span className="episode-pin-title">{ep.title}</span>
          </button>
        );
      })}
    </div>
  );
}
