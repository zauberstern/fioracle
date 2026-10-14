import kaplay from "kaplay";
import { loadDeskAssets } from "./assets/manifest";
import { gameState } from "./gameState";
import { registerTitleScene } from "./scenes/TitleScene";
import { registerDeskScene } from "./scenes/AsOfDeskScene";
import { registerCrashScene } from "./scenes/CrashScene";
import { registerDebriefScene } from "./scenes/DebriefScene";

const root = document.querySelector("#game");
if (!root) {
  throw new Error("Missing #game root element");
}

const k = kaplay({
  width: 960,
  height: 540,
  stretch: true,
  letterbox: true,
  background: [58, 52, 44],
  global: false,
  root: root as HTMLElement,
  touchToMouse: true,
  // Keep iframe from stealing focus until Title click-to-play.
  crisp: true,
  // Prefer 60fps; parent dashboard shares the frame budget.
  maxFPS: 60,
} as Parameters<typeof kaplay>[0]);

const assetsReady = loadDeskAssets(
  k as unknown as Parameters<typeof loadDeskAssets>[0]
);
guardDrawText(k as unknown as Parameters<typeof guardDrawText>[0]);
gameState.audio.bind(k);
gameState.juice.bind(k, gameState.audio);
gameState.bridge.start();

const reduced =
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
if (reduced) gameState.juice.setReducedMotion(true);

const saved = gameState.portfolio.restore();
if (saved) {
  if (typeof saved.turn === "number") gameState.sessionTurns = saved.turn as number;
  if (typeof saved.scoreCumulative === "number") {
    /* score reset on new session from title; keep weights only across remount mid-desk */
  }
}

registerTitleScene(k, gameState);
registerDeskScene(k, gameState);
registerCrashScene(k, gameState);
registerDebriefScene(k, gameState);

let started = false;
const goTitle = () => {
  if (started) return;
  started = true;
  void gameState.tape
    .load()
    .then((ok) => {
      if (!ok) {
        gameState.bridge.post({
          type: "error",
          message: gameState.tape.errorMessage || "No history",
        });
      }
      k.go("title");
    })
    .catch((err) => {
      gameState.bridge.post({
        type: "error",
        message: String(err),
      });
      k.go("title");
    });
};

function spriteReady(name: string): boolean {
  const getter = (k as { getSprite?: (n: string) => { data?: unknown } | null }).getSprite;
  if (typeof getter !== "function") return false;
  const spr = getter.call(k, name);
  return Boolean(spr && spr.data);
}

// Queue the atlases first. onLoad on an empty asset map already reports done.
assetsReady
  .then(() => {
    const onLoad = (k as { onLoad?: (cb: () => void) => void }).onLoad;
    if (typeof onLoad === "function") onLoad.call(k, goTitle);
    else goTitle();
  })
  .catch((err) => {
    gameState.bridge.post({
      type: "error",
      message: err instanceof Error ? err.message : String(err),
    });
    goTitle();
  });

setTimeout(() => {
  if (started) return;
  if (!spriteReady("player_s")) {
    gameState.bridge.post({
      type: "error",
      message: "Town art is still loading.",
    });
  }
  goTitle();
}, 3000);

function guardDrawText(ctx: {
  drawText: (opt: { text: string; font?: unknown }) => void;
  getFont?: (name: string) => unknown;
}): void {
  const raw = ctx.drawText.bind(ctx);
  ctx.drawText = (opt) => {
    try {
      if (
        typeof opt.font === "string" &&
        typeof ctx.getFont === "function" &&
        !ctx.getFont(opt.font)
      ) {
        return;
      }
      raw(opt);
    } catch {
      try {
        raw({ ...opt, font: "monospace" });
      } catch {
        /* skip this frame */
      }
    }
  };
}
