import type { KAPLAYCtx } from "kaplay";
import type { DeskHud } from "../systems/TapePlayer";

export class MarketTicker {
  private scroll = 0;

  tick(dt: number): void {
    this.scroll += dt * 24;
    if (this.scroll > 400) this.scroll = 0;
  }

  draw(k: KAPLAYCtx, asOf: string, hud: DeskHud, source: string): void {
    const sent = Number.isFinite(hud.sentiment) ? hud.sentiment.toFixed(2) : "n/a";
    const line = `AS OF ${asOf} | HEAT ${hud.heat.toFixed(2)} | STRETCH ${hud.stretch.toFixed(2)} | CRASH ${hud.crashWindow} | SENT ${sent} | ${hud.regime} | ${source}`;
    k.drawRect({
      pos: k.vec2(0, 0),
      width: k.width(),
      height: 14,
      color: k.rgb(12, 16, 28),
    });
    k.drawText({
      text: line,
      pos: k.vec2(4 - this.scroll, 3),
      size: 8,
      color: k.rgb(120, 200, 255),
    });
  }
}
