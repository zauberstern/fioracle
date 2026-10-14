import type { KAPLAYCtx } from "kaplay";
import { EPISODES } from "../../../shared/episodes";
import { plainDate } from "../../../shared/plainDate";
import type { GameState } from "../gameState";
import { CANVAS } from "../ui/layout";
import { STAND_IN } from "../ui/tutorialCopy";
import { TYPE } from "../ui/type";

const STONE_TITLES: Record<string, string> = {
  dotcom: "The Opening",
  gfc: "The House that Fell",
  covid: "The White Day",
  tightening: "The Tight Year",
  banks23: "The Vault Run",
};

export function registerTitleScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("title", () => {
    let episodeIdx = 0;
    let veilDismissed = gs.focused;

    const focusCanvas = () => {
      const canvas = k.canvas;
      canvas?.focus({ preventScroll: true });
      gs.focused = true;
      veilDismissed = true;
      gs.audio.unlock();
      gs.juice.uiClick();
      gs.bridge.post({ type: "ready" });
    };

    const startDesk = () => {
      if (!gs.tape.hasTape) return;
      gs.score.resetSession();
      gs.sessionTurns = 0;
      gs.crashTriggered = false;
      gs.crashReason = "";
      gs.portfolio.resetEqual();
      gs.lastBreakdown = null;
      if (gs.episodePickedByUser) {
        const ep = EPISODES[episodeIdx]!;
        gs.tape.jumpToDate(ep.date);
      } else if (gs.parentAsOf) {
        gs.tape.jumpToDate(gs.parentAsOf);
      } else {
        const ep = EPISODES[episodeIdx]!;
        gs.tape.jumpToDate(ep.date);
      }
      gs.juice.uiClick();
      k.go("desk");
    };

    k.onClick(() => {
      if (!veilDismissed) {
        focusCanvas();
        return;
      }
      startDesk();
    });

    k.onKeyPress("enter", () => {
      if (!veilDismissed) {
        focusCanvas();
        return;
      }
      startDesk();
    });

    k.onKeyPress("left", () => {
      episodeIdx = (episodeIdx - 1 + EPISODES.length) % EPISODES.length;
      gs.episodePickedByUser = true;
      gs.juice.uiClick();
    });
    k.onKeyPress("right", () => {
      episodeIdx = (episodeIdx + 1) % EPISODES.length;
      gs.episodePickedByUser = true;
      gs.juice.uiClick();
    });
    for (let i = 1; i <= 5; i++) {
      k.onKeyPress(String(i), () => {
        episodeIdx = i - 1;
        gs.episodePickedByUser = true;
        const ep = EPISODES[episodeIdx];
        if (ep) gs.tape.jumpToDate(ep.date);
        gs.juice.uiClick();
      });
    }

    gs.bridge.setHandlers({
      onEpisode: (id) => {
        const idx = EPISODES.findIndex((e) => e.id === id);
        if (idx >= 0) {
          episodeIdx = idx;
          gs.episodePickedByUser = true;
          gs.tape.jumpToDate(EPISODES[idx]!.date);
        }
      },
      onAsOf: (date) => {
        gs.parentAsOf = date;
        if (!gs.episodePickedByUser) gs.tape.jumpToDate(date);
      },
      onMute: (m) => gs.audio.setMuted(m),
      onReducedMotion: (on) => gs.juice.setReducedMotion(on),
      onPause: () => {
        gs.paused = true;
      },
      onResume: () => {
        gs.paused = false;
        if (!veilDismissed) focusCanvas();
      },
    });
    gs.bridge.post({ type: "boot" });

    k.onDraw(() => {
      k.drawRect({
        pos: k.vec2(0, 0),
        width: CANVAS.w,
        height: CANVAS.h,
        color: k.rgb(58, 52, 44),
      });
      k.drawRect({
        pos: k.vec2(80, 40),
        width: CANVAS.w - 160,
        height: CANVAS.h - 80,
        color: k.rgb(216, 201, 168),
        outline: { width: 3, color: k.rgb(176, 141, 79) },
      });
      k.drawText({
        text: "Stillmoor",
        pos: k.vec2(CANVAS.w / 2, 72),
        anchor: "center",
        font: TYPE.title.font,
        size: TYPE.title.size,
        color: k.rgb(42, 36, 28),
      });
      k.drawText({
        text: `History: ${gs.tape.dataSource}`,
        pos: k.vec2(CANVAS.w / 2, 108),
        anchor: "center",
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color:
          gs.tape.dataSource === "empty"
            ? k.rgb(42, 36, 28)
            : k.rgb(42, 36, 28),
      });
      if (gs.tape.dataSource === "empty") {
        k.drawText({
          text: gs.tape.errorMessage || "No history yet. Export the compass pages first.",
          pos: k.vec2(CANVAS.w / 2, 132),
          anchor: "center",
          font: TYPE.chat.font,
          size: TYPE.chat.size,
          color: k.rgb(42, 36, 28),
        });
      }

      const ep = EPISODES[episodeIdx]!;
      const title = STONE_TITLES[ep.id] ?? ep.title;
      const startHint = gs.episodePickedByUser
        ? `${title}  (${plainDate(ep.date)})`
        : gs.parentAsOf
          ? `Weekly reading  (${plainDate(gs.parentAsOf)})`
          : `${title}  (${plainDate(ep.date)})`;
      k.drawText({
        text: startHint,
        pos: k.vec2(CANVAS.w / 2, 180),
        anchor: "center",
        font: TYPE.stamp.font,
        size: TYPE.stamp.size,
        color: k.rgb(42, 36, 28),
      });
      k.drawText({
        text: ep.blurb,
        pos: k.vec2(CANVAS.w / 2, 208),
        anchor: "center",
        font: TYPE.chat.font,
        size: TYPE.chat.size,
        color: k.rgb(42, 36, 28),
        width: 640,
        align: "center",
      });

      k.drawText({
        text: "Left and right pick a flood stone. Keys 1 to 5 jump. Enter walks in.",
        pos: k.vec2(CANVAS.w / 2, 300),
        anchor: "center",
        font: TYPE.chat.font,
        size: TYPE.chat.size,
        color: k.rgb(42, 36, 28),
      });
      k.drawText({
        text: STAND_IN,
        pos: k.vec2(CANVAS.w / 2, 336),
        anchor: "center",
        font: TYPE.chat.font,
        size: TYPE.chat.size,
        color: k.rgb(42, 36, 28),
        width: 760,
        align: "center",
      });

      if (!veilDismissed) {
        k.drawRect({
          pos: k.vec2(0, 0),
          width: CANVAS.w,
          height: CANVAS.h,
          color: k.rgb(42, 36, 28),
          opacity: 0.82,
        });
        k.drawText({
          text: "Click once. That unlocks sound and the keys.",
          pos: k.vec2(CANVAS.w / 2, CANVAS.h / 2),
          anchor: "center",
          font: TYPE.chat.font,
          size: TYPE.chat.size,
          color: k.rgb(216, 201, 168),
        });
      }
    });
  });
}
