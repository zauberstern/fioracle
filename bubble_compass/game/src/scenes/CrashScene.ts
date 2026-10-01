import type { KAPLAYCtx } from "kaplay";
import type { gameState } from "../gameState";
import { FireSaleCascade } from "../systems/FireSaleCascade";
import type { TurnScoreBreakdown } from "../systems/ScoreKeeper";

type GameState = typeof gameState;

export function registerCrashScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("crash", (opts?: { breakdown?: TurnScoreBreakdown }) => {
    const cascade = new FireSaleCascade();
    const nodes = [
      { id: "HY", exposure: 0.4 },
      { id: "IG", exposure: 0.25 },
      { id: "EQ", exposure: 0.35 },
    ];
    const adjacency = [
      [0, 0.6, 0.3],
      [0.5, 0, 0.4],
      [0.2, 0.3, 0],
    ];
    cascade.reset(nodes, adjacency);
    const breakdown = opts?.breakdown;

    k.onUpdate(() => {
      cascade.tick(k.dt());
    });

    k.onDraw(() => {
      k.drawRect({
        pos: k.vec2(0, 0),
        width: k.width(),
        height: k.height(),
        color: k.rgb(28, 8, 8),
      });
      k.drawText({
        text: "FIRE SALE CASCADE",
        pos: k.vec2(k.width() / 2, 24),
        size: 14,
        anchor: "center",
        color: k.rgb(255, 120, 80),
      });
      k.drawText({
        text: `as of ${gs.tape.currentAsOf()}`,
        pos: k.vec2(k.width() / 2, 42),
        size: 9,
        anchor: "center",
        color: k.rgb(220, 180, 160),
      });
      cascade.draw(k, 40, 90);
      if (breakdown) {
        k.drawText({
          text: `turn loss ${(breakdown.portfolioReturn * 100).toFixed(2)}%`,
          pos: k.vec2(k.width() / 2, 150),
          size: 10,
          anchor: "center",
          color: k.rgb(255, 200, 180),
        });
      }
      k.drawText({
        text: "space: continue",
        pos: k.vec2(k.width() / 2, k.height() - 12),
        size: 8,
        anchor: "center",
        color: k.rgb(200, 160, 150),
      });
    });

    k.onKeyPress("space", () => {
      if (gs.sessionTurns >= gs.maxTurnsPerSession || !gs.tape.advance()) {
        k.go("debrief");
        return;
      }
      k.go("desk");
    });
  });
}
