import type { KAPLAYCtx } from "kaplay";
import { Sleeve } from "../entities/Sleeve";
import { MarketTicker } from "../entities/MarketTicker";
import type { gameState } from "../gameState";
import { CreditSurfaceVisualizer } from "../systems/CreditSurfaceVisualizer";
import type { TurnScoreBreakdown } from "../systems/ScoreKeeper";

type GameState = typeof gameState;

export function registerDeskScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("desk", () => {
    const ticker = new MarketTicker();
    const surface = new CreditSurfaceVisualizer();
    const sleeves = Sleeve.catalog();
    let lastBreakdown: TurnScoreBreakdown | null = null;
    let statusMsg = "arrows: sleeve  w/s: weight  space: commit";

    k.onUpdate(() => {
      ticker.tick(k.dt());
    });

    k.onDraw(() => {
      k.drawRect({
        pos: k.vec2(0, 0),
        width: k.width(),
        height: k.height(),
        color: k.rgb(14, 16, 26),
      });

      const hud = gs.tape.benchmarkHud();
      ticker.draw(k, gs.tape.currentAsOf(), hud, gs.tape.dataSource);

      const barTop = 18;
      const barH = 10;
      sleeves.forEach((sleeve, i) => {
        const w = gs.portfolio.weights[sleeve.def.id] ?? 0;
        const [r, g, b] = sleeve.parseColor();
        const y = barTop + i * (barH + 2);
        const selected = gs.portfolio.selectedIndex === i;
        k.drawRect({
          pos: k.vec2(4, y),
          width: k.width() - 8,
          height: barH,
          color: k.rgb(30, 32, 44),
        });
        k.drawRect({
          pos: k.vec2(4, y),
          width: (k.width() - 8) * w,
          height: barH,
          color: k.rgb(r, g, b),
        });
        if (selected) {
          k.drawRect({
            pos: k.vec2(2, y - 1),
            width: k.width() - 4,
            height: barH + 2,
            outline: { width: 1, color: k.rgb(255, 255, 255) },
          });
        }
        k.drawText({
          text: `${sleeve.def.label} ${(w * 100).toFixed(0)}%`,
          pos: k.vec2(6, y + 1),
          size: 7,
          color: k.rgb(240, 240, 250),
        });
      });

      const samples = [
        { spreadBps: hud.spreadBps * 0.9, ltv: hud.ltv * 0.95 },
        { spreadBps: hud.spreadBps, ltv: hud.ltv },
        { spreadBps: hud.spreadBps * 1.08, ltv: Math.min(0.95, hud.ltv + 0.04) },
      ];
      surface.draw(k, {
        x: 8,
        y: k.height() - 52,
        width: k.width() - 16,
        height: 28,
        samples,
      });

      k.drawText({
        text: `turn ${gs.sessionTurns + 1}/${gs.maxTurnsPerSession}  score ${gs.score.totalScore.toFixed(4)}`,
        pos: k.vec2(4, k.height() - 62),
        size: 8,
        color: k.rgb(180, 200, 220),
      });
      k.drawText({
        text: statusMsg,
        pos: k.vec2(4, k.height() - 10),
        size: 7,
        color: k.rgb(130, 140, 160),
      });

      if (lastBreakdown) {
        k.drawText({
          text: `last dP ${(lastBreakdown.portfolioReturn * 100).toFixed(2)}%`,
          pos: k.vec2(k.width() - 4, k.height() - 62),
          size: 8,
          anchor: "topright",
          color: k.rgb(255, 200, 120),
        });
      }
    });

    k.onKeyPress("up", () => gs.portfolio.selectPrev());
    k.onKeyPress("down", () => gs.portfolio.selectNext());
    k.onKeyPress("w", () => gs.portfolio.bumpSelected(0.05));
    k.onKeyPress("s", () => gs.portfolio.bumpSelected(-0.05));

    k.onKeyPress("space", () => {
      if (!gs.tape.hasTape) return;
      const returns: Record<string, number> = {};
      for (const s of sleeves) {
        returns[s.def.id] = gs.tape.sleeveDailyReturn(s.def.id);
      }
      lastBreakdown = gs.score.scoreTurn(gs.portfolio, returns);
      gs.lastTurnScore = lastBreakdown.total;
      gs.sessionTurns += 1;

      const hud = gs.tape.benchmarkHud();
      const bust =
        hud.regime === "bust" ||
        (hud.stretch > 2 && lastBreakdown.portfolioReturn < -0.02);
      gs.crashTriggered = bust;

      if (bust) {
        k.go("crash", { breakdown: lastBreakdown });
        return;
      }

      if (gs.sessionTurns >= gs.maxTurnsPerSession || !gs.tape.advance()) {
        k.go("debrief");
        return;
      }
      statusMsg = `committed ${gs.tape.currentAsOf()}`;
    });

    k.onKeyPress("escape", () => k.go("title"));
  });
}
