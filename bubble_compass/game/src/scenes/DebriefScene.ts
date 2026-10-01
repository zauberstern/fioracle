import type { KAPLAYCtx } from "kaplay";
import type { gameState } from "../gameState";

type GameState = typeof gameState;

export function registerDebriefScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("debrief", () => {
    k.onDraw(() => {
      k.drawRect({
        pos: k.vec2(0, 0),
        width: k.width(),
        height: k.height(),
        color: k.rgb(10, 14, 22),
      });
      k.drawText({
        text: "SESSION DEBRIEF",
        pos: k.vec2(k.width() / 2, 28),
        size: 14,
        anchor: "center",
        color: k.rgb(140, 220, 180),
      });
      k.drawText({
        text: `turns played: ${gs.sessionTurns}`,
        pos: k.vec2(k.width() / 2, 52),
        size: 9,
        anchor: "center",
        color: k.rgb(200, 200, 220),
      });
      k.drawText({
        text: `cumulative score: ${gs.score.totalScore.toFixed(4)}`,
        pos: k.vec2(k.width() / 2, 68),
        size: 10,
        anchor: "center",
        color: k.rgb(255, 220, 140),
      });
      k.drawText({
        text: gs.crashTriggered ? "crash window hit this session" : "no crash scene triggered",
        pos: k.vec2(k.width() / 2, 88),
        size: 8,
        anchor: "center",
        color: k.rgb(160, 160, 180),
      });
      k.drawText({
        text: "enter: title",
        pos: k.vec2(k.width() / 2, k.height() - 16),
        size: 8,
        anchor: "center",
        color: k.rgb(120, 120, 140),
      });
    });

    k.onKeyPress("enter", () => {
      k.go("title");
    });
  });
}
