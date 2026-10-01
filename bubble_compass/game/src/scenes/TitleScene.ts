import type { KAPLAYCtx } from "kaplay";
import episodes from "../data/episodes.json";
import type { gameState } from "../gameState";

type GameState = typeof gameState;

export function registerTitleScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("title", () => {
    let episodeCursor = 0;

    k.onDraw(() => {
      k.drawRect({
        pos: k.vec2(0, 0),
        width: k.width(),
        height: k.height(),
        color: k.rgb(8, 10, 20),
      });
      k.drawText({
        text: "BUBBLE COMPASS",
        pos: k.vec2(k.width() / 2, 36),
        size: 16,
        anchor: "center",
        color: k.rgb(100, 180, 255),
      });

      if (!gs.tape.hasTape) {
        k.drawText({
          text: "TAPE NOT BUILT",
          pos: k.vec2(k.width() / 2, 68),
          size: 12,
          anchor: "center",
          color: k.rgb(255, 80, 80),
        });
        k.drawText({
          text: "build /history on API or use fixture",
          pos: k.vec2(k.width() / 2, 84),
          size: 8,
          anchor: "center",
          color: k.rgb(180, 140, 140),
        });
      } else {
        k.drawText({
          text: `tape: ${gs.tape.dataSource} (${gs.tape.timelineLength}d)`,
          pos: k.vec2(k.width() / 2, 68),
          size: 9,
          anchor: "center",
          color: k.rgb(140, 200, 160),
        });
      }

      const ep = episodes.episodes[episodeCursor];
      k.drawText({
        text: `[${episodeCursor + 1}] ${ep.title}`,
        pos: k.vec2(k.width() / 2, 110),
        size: 10,
        anchor: "center",
        color: k.rgb(220, 220, 240),
      });
      k.drawText({
        text: ep.subtitle,
        pos: k.vec2(k.width() / 2, 124),
        size: 8,
        anchor: "center",
        color: k.rgb(150, 150, 170),
      });

      k.drawText({
        text: "arrows: episode  enter: desk  1-5: jump",
        pos: k.vec2(k.width() / 2, k.height() - 16),
        size: 8,
        anchor: "center",
        color: k.rgb(120, 120, 140),
      });
    });

    k.onKeyPress("left", () => {
      episodeCursor = (episodeCursor - 1 + episodes.episodes.length) % episodes.episodes.length;
    });
    k.onKeyPress("right", () => {
      episodeCursor = (episodeCursor + 1) % episodes.episodes.length;
    });

    for (let i = 1; i <= 5; i++) {
      k.onKeyPress(String(i), () => {
        episodeCursor = i - 1;
        if (gs.tape.hasTape) {
          gs.tape.jumpToDate(episodes.episodes[episodeCursor].asOf);
        }
      });
    }

    k.onKeyPress("enter", () => {
      if (!gs.tape.hasTape) return;
      gs.portfolio.reset();
      gs.score.resetSession();
      gs.sessionTurns = 0;
      gs.crashTriggered = false;
      gs.tape.jumpToDate(episodes.episodes[episodeCursor].asOf);
      k.go("desk");
    });
  });
}
