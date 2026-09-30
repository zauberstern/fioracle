/** Embed As-Of Desk. On Pages build, desk lives next to the dashboard. */
const GAME_URL =
  import.meta.env.VITE_GAME_URL ||
  `${import.meta.env.BASE_URL || "/"}desk/`;

export function GameEmbed() {
  return (
    <div className="game-embed">
      <div className="game-embed-banner">
        As-Of Desk plays the same history tape as the dashboard. No synthetic events.
      </div>
      <iframe
        title="As-Of Desk"
        src={GAME_URL}
        className="game-embed-frame"
        allow="autoplay"
      />
      <p className="game-embed-help">
        Opens the desk at <code>{GAME_URL}</code>. Locally, run{" "}
        <code>cd bubble_compass/game && npm run dev</code> if the frame is blank.
      </p>
    </div>
  );
}
