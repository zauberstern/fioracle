import type { KAPLAYCtx } from "kaplay";
import { plainDate } from "../../../shared/plainDate";
import { Sleeve } from "../entities/Sleeve";
import type { GameState } from "../gameState";
import { FireSaleCascade } from "../systems/FireSaleCascade";
import type { TurnScoreBreakdown } from "../systems/ScoreKeeper";
import { examineGravestone } from "../ui/Examine";
import { TYPE } from "../ui/type";

export function registerCrashScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene(
    "crash",
    (opts?: { breakdown?: TurnScoreBreakdown; reason?: string }) => {
      const cascade = new FireSaleCascade();
      const sleeves = Sleeve.catalog();
      const breakdown = opts?.breakdown ?? gs.lastBreakdown;
      const reason = opts?.reason ?? gs.crashReason ?? "history threshold";

      const nodes = sleeves
        .map((s, i) => {
          const w = gs.portfolio.weights[s.def.id] ?? 0;
          const raw = gs.tape.sleeveDailyReturn(s.def.id);
          const r = Number.isFinite(raw) ? raw : 0;
          return {
            id: s.def.id,
            weight: w,
            contribution: w * r,
            color: s.def.color,
            chipIndex: i,
          };
        })
        .filter((n) => n.weight > 0);

      cascade.reducedMotion = gs.juice.reducedMotion;
      cascade.reset(nodes);
      if (!gs.juice.reducedMotion) gs.juice.cascadeHit();

      // Mute/pause only: no onAsOf that jumps the tape during the cascade.
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

      let elapsed = 0;
      const autoAdvance = 2.4;
      let done = false;

      const leave = () => {
        if (done) return;
        done = true;
        // Commit skipped advance on the gate path; leave advances once.
        const atEnd =
          gs.sessionTurns >= gs.maxTurnsPerSession || !gs.tape.advance();
        gs.bridge.post({
          type: "turnCommitted",
          asOf: gs.tape.currentAsOf(),
          weights: gs.portfolio.weights,
          score: gs.lastTurnScore,
        });
        gs.ignoreInboundAsOf = false;
        if (atEnd) {
          k.go("debrief");
          return;
        }
        gs.crashTriggered = false;
        k.go("desk");
      };

      k.onUpdate(() => {
        const finished = cascade.update(k.dt());
        elapsed += k.dt();
        if (finished && elapsed >= autoAdvance) leave();
      });

      k.onDraw(() => {
        k.drawRect({
          pos: k.vec2(0, 0),
          width: k.width(),
          height: k.height(),
          color: k.rgb(42, 36, 28),
        });
        // Gravestone silhouette
        k.drawRect({
          pos: k.vec2(k.width() / 2 - 40, 48),
          width: 80,
          height: 100,
          color: k.rgb(92, 83, 70),
          outline: { width: 2, color: k.rgb(176, 141, 79) },
        });
        k.drawEllipse({
          pos: k.vec2(k.width() / 2, 48),
          radiusX: 40,
          radiusY: 18,
          color: k.rgb(92, 83, 70),
        });
        k.drawText({
          text: examineGravestone(),
          pos: k.vec2(k.width() / 2, 170),
          font: TYPE.stamp.font,
          size: TYPE.stamp.size,
          anchor: "center",
          color: k.rgb(216, 201, 168),
          width: 720,
          align: "center",
        });
        k.drawText({
          text: `as of ${plainDate(gs.tape.currentAsOf())}  |  ${reason}`,
          pos: k.vec2(k.width() / 2, 200),
          font: TYPE.hud.font,
          size: TYPE.hud.size,
          anchor: "center",
          color: k.rgb(232, 228, 217),
          width: 800,
          align: "center",
        });
        cascade.draw(k, 80, 220, k.width() - 160, 200);
        if (breakdown) {
          k.drawText({
            text: `turn print ${(breakdown.portfolioReturn * 100).toFixed(2)}%`,
            pos: k.vec2(k.width() / 2, 440),
            font: TYPE.hud.font,
            size: TYPE.hud.size,
            anchor: "center",
            color: k.rgb(216, 201, 168),
          });
        }
        k.drawText({
          text: "Space continues",
          pos: k.vec2(k.width() / 2, k.height() - 24),
          font: TYPE.chat.font,
          size: TYPE.chat.size,
          anchor: "center",
          color: k.rgb(232, 228, 217),
        });
      });

      k.onKeyPress("space", leave);
      k.onClick(leave);
    }
  );
}
