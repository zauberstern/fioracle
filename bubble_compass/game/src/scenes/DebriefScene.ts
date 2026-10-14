import type { KAPLAYCtx } from "kaplay";
import { EPISODES } from "../../../shared/episodes";
import { plainDate } from "../../../shared/plainDate";
import type { GameState } from "../gameState";
import { albumDebriefLine } from "../systems/StampAlbum";
import { TYPE } from "../ui/type";

export function registerDebriefScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("debrief", () => {
    // Mute/pause only: no onAsOf that jumps the tape on the ledger.
    gs.bridge.setHandlers({
      onMute: (m) => gs.audio.setMuted(m),
      onReducedMotion: (on) => gs.juice.setReducedMotion(on),
      onPause: () => {
        gs.paused = true;
      },
      onResume: () => {
        gs.paused = false;
      },
    });

    // Desk already advanced on the stamp path; continue from that tip.
    const continueAt = gs.tape.currentAsOf();
    gs.parentAsOf = continueAt;

    const bd = gs.lastBreakdown;
    const belief = !bd
      ? "No day scored on this trip."
      : bd.skillVsBench > 0
        ? "On the last day that scored, the book beat the bench."
        : "On the last day that scored, the book did not beat the bench.";
    const tape = `The history ends at ${plainDate(continueAt)}, after ${gs.sessionTurns} stamps (source ${gs.tape.dataSource}).`;
    const gap = gs.crashTriggered
      ? `The crash gate opened (${gs.crashReason || "threshold"}).`
      : "The crash gate did not open on this trip.";
    const atTapeEnd = gs.tape.peekNextAsOf() == null;
    const next = atTapeEnd
      ? "This is the end of the history. Head back to the weekly reading."
      : `The book is waiting at ${plainDate(continueAt)}. You can skip days. There is no streak.`;
    const albumBody = albumDebriefLine(gs.album.list());
    const tour = gs.town.tourLine(EPISODES.map((e) => e.date));
    const nextWithTour = tour ? `${next} ${tour}` : next;

    k.onDraw(() => {
      k.drawRect({
        pos: k.vec2(0, 0),
        width: k.width(),
        height: k.height(),
        color: k.rgb(58, 52, 44),
      });
      k.drawRect({
        pos: k.vec2(60, 28),
        width: k.width() - 120,
        height: k.height() - 56,
        color: k.rgb(216, 201, 168),
        outline: { width: 3, color: k.rgb(176, 141, 79) },
      });
      k.drawText({
        text: "The trip ledger",
        pos: k.vec2(k.width() / 2, 52),
        font: TYPE.title.font,
        size: TYPE.title.size,
        anchor: "center",
        color: k.rgb(42, 36, 28),
      });
      k.drawText({
        text: `score ${gs.score.totalScore.toFixed(4)}   album ${gs.album.count()}   max DD ${(gs.score.peakDrawdown * 100).toFixed(2)}%   crash ${gs.crashTriggered ? "yes" : "no"}`,
        pos: k.vec2(k.width() / 2, 84),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        anchor: "center",
        color: k.rgb(42, 36, 28),
      });

      const blocks = [
        { title: "What you held", body: belief },
        { title: "The history", body: tape },
        { title: "The gate", body: gap },
        { title: "The album", body: albumBody },
        { title: "Next", body: nextWithTour },
      ];
      blocks.forEach((b, i) => {
        const y = 100 + i * 82;
        k.drawRect({
          pos: k.vec2(100, y),
          width: k.width() - 200,
          height: 80,
          color: k.rgb(232, 228, 217),
          outline: { width: 1, color: k.rgb(42, 36, 28) },
        });
        k.drawText({
          text: b.title,
          pos: k.vec2(116, y + 8),
          font: TYPE.hud.font,
          size: TYPE.hud.size,
          color: k.rgb(42, 36, 28),
        });
        k.drawText({
          text: b.body,
          pos: k.vec2(116, y + 26),
          font: TYPE.chat.font,
          size: TYPE.chat.size,
          color: k.rgb(42, 36, 28),
          width: k.width() - 240,
        });
      });

      k.drawText({
        text: "Enter returns to the title",
        pos: k.vec2(k.width() / 2, k.height() - 40),
        font: TYPE.chat.font,
        size: TYPE.chat.size,
        anchor: "center",
        color: k.rgb(42, 36, 28),
      });
    });

    const toTitle = () => {
      gs.juice.uiClick();
      // Next title visit continues the tape unless the player picks a stone.
      gs.episodePickedByUser = false;
      k.go("title");
    };
    k.onKeyPress("enter", toTitle);
    k.onClick(toTitle);
  });
}
