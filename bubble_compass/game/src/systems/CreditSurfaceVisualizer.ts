import type { KAPLAYCtx } from "kaplay";
import { TYPE } from "../ui/type";

/** OAS sparkline only - never invent LTV. */

export class CreditSurfaceVisualizer {
  draw(
    k: KAPLAYCtx,
    opts: {
      x: number;
      y: number;
      width: number;
      height: number;
      oasHistory: number[];
    }
  ): void {
    const { x, y, width, height, oasHistory } = opts;
    k.drawRect({
      pos: k.vec2(x, y),
      width,
      height,
      color: k.rgb(20, 20, 31),
      outline: { width: 1, color: k.rgb(42, 42, 58) },
    });
    if (oasHistory.length < 3) {
      k.drawText({
        text: "surface unavailable (no LTV; OAS history < 3)",
        pos: k.vec2(x + 6, y + height / 2 - 4),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(138, 138, 154),
      });
      return;
    }
    const min = Math.min(...oasHistory);
    const max = Math.max(...oasHistory);
    const span = Math.max(max - min, 1e-6);
    const step = (width - 12) / (oasHistory.length - 1);
    for (let i = 1; i < oasHistory.length; i++) {
      const x0 = x + 6 + (i - 1) * step;
      const x1 = x + 6 + i * step;
      const y0 = y + height - 6 - ((oasHistory[i - 1]! - min) / span) * (height - 12);
      const y1 = y + height - 6 - ((oasHistory[i]! - min) / span) * (height - 12);
      k.drawLine({
        p1: k.vec2(x0, y0),
        p2: k.vec2(x1, y1),
        width: 2,
        color: k.rgb(230, 159, 0),
      });
    }
    k.drawText({
      text: `HY OAS ${oasHistory[oasHistory.length - 1]!.toFixed(0)} bps`,
      pos: k.vec2(x + 6, y + 4),
      font: TYPE.hud.font,
      size: TYPE.hud.size,
      color: k.rgb(232, 228, 217),
    });
  }
}
