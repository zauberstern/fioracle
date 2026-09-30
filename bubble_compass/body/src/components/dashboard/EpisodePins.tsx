import { EPISODES } from "../../copy/episodes";
import { useMarketStore } from "../../store/marketStore";

export function EpisodePins() {
  const jumpToEpisode = useMarketStore((s) => s.jumpToEpisode);
  const replayTimestamp = useMarketStore((s) => s.replayTimestamp);

  return (
    <div className="episode-pins" aria-label="Historical episodes">
      {EPISODES.map((ep) => {
        const active =
          replayTimestamp != null &&
          Math.abs(replayTimestamp - Math.floor(new Date(ep.date).getTime() / 1000)) <
            86400 * 3;
        return (
          <button
            key={ep.id}
            type="button"
            className="episode-pin"
            data-active={active ? "true" : "false"}
            title={ep.blurb}
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
