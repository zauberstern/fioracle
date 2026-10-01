import kaplay from "kaplay";
import crtFrag from "./shaders/crt.frag?raw";
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
  width: 320,
  height: 200,
  scale: 2,
  stretch: true,
  letterbox: true,
  background: [10, 10, 18],
  global: false,
  root: root as HTMLElement,
  touchToMouse: true,
});

k.loadShader("crt", null, crtFrag);

function mountCrtOverlay(): void {
  const overlay = k.add([k.fixed(), k.stay(), k.z(10000)]);
  overlay.onDraw(() => {
    const t = k.time();
    for (let y = 0; y < k.height(); y += 2) {
      const flicker = 0.08 + 0.04 * Math.sin(t * 3 + y * 0.2);
      k.drawRect({
        pos: k.vec2(0, y),
        width: k.width(),
        height: 1,
        color: k.rgb(0, 0, 0),
        opacity: flicker,
      });
    }
  });
}

k.onLoad(() => {
  mountCrtOverlay();
});

registerTitleScene(k, gameState);
registerDeskScene(k, gameState);
registerCrashScene(k, gameState);
registerDebriefScene(k, gameState);

void gameState.tape.load().then(() => {
  k.go("title");
});
