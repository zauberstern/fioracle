import { plainDate } from "../../../shared/plainDate";
import type { DeskHud } from "../systems/TapePlayer";

/** Chat consumes one tape line; no scrolling bar on the HUD. */
export class MarketTicker {
  private scroll = 0;
  private paused = false;

  setPaused(p: boolean): void {
    this.paused = p;
  }

  togglePaused(): void {
    this.paused = !this.paused;
  }

  tick(dt: number): void {
    if (this.paused) return;
    this.scroll += dt * 48;
    if (this.scroll > 600) this.scroll = 0;
  }

  line(asOf: string, hud: DeskHud, source: string): string {
    const sent = Number.isFinite(hud.sentiment)
      ? hud.sentiment.toFixed(2)
      : "n/a";
    const oas = Number.isFinite(hud.spreadBps)
      ? `${hud.spreadBps.toFixed(0)}bps`
      : "n/a";
    return `${plainDate(asOf)}  heat ${hud.heat.toFixed(0)}  stretch ${hud.stretch.toFixed(2)}  regime ${hud.regime}  sent ${sent}  OAS ${oas}  history ${source}`;
  }

  /** @deprecated Prefer chat.line; kept for any residual callers. */
  draw(): void {
    /* no bar */
  }
}
