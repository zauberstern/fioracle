import type { KAPLAYCtx } from "kaplay";

export interface CreditSurfaceSample {
  spreadBps: number;
  ltv: number;
}

export interface CreditSurfaceDrawOpts {
  x: number;
  y: number;
  width: number;
  height: number;
  samples: CreditSurfaceSample[];
}

/** Spread-vs-LTV terrain; steepening slope signals instability. */
export class CreditSurfaceVisualizer {
  instability(samples: CreditSurfaceSample[]): number {
    if (samples.length < 2) return 0;
    let maxSlope = 0;
    for (let i = 1; i < samples.length; i++) {
      const a = samples[i - 1];
      const b = samples[i];
      const dSpread = b.spreadBps - a.spreadBps;
      const dLtv = b.ltv - a.ltv;
      if (Math.abs(dLtv) < 1e-6) continue;
      const slope = dSpread / (dLtv * 1000);
      maxSlope = Math.max(maxSlope, Math.abs(slope));
    }
    return Math.min(1, maxSlope);
  }

  draw(k: KAPLAYCtx, opts: CreditSurfaceDrawOpts): void {
    const { x, y, width, height, samples } = opts;
    if (samples.length === 0) return;

    const maxSpread = Math.max(...samples.map((s) => s.spreadBps), 100);
    const instab = this.instability(samples);

    k.drawRect({
      pos: k.vec2(x, y),
      width,
      height,
      color: k.rgb(20, 24, 36),
    });

    const pts: { px: number; py: number }[] = [];
    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      const px = x + (s.ltv * width);
      const py = y + height - (s.spreadBps / maxSpread) * (height - 4);
      pts.push({ px, py });
    }

    for (let i = 1; i < pts.length; i++) {
      k.drawLine({
        p1: k.vec2(pts[i - 1].px, pts[i - 1].py),
        p2: k.vec2(pts[i].px, pts[i].py),
        width: 2,
        color: k.rgb(180, 100 + instab * 120, 80),
      });
    }

    k.drawText({
      text: `surface ${(instab * 100).toFixed(0)}% steep`,
      pos: k.vec2(x + 2, y + 2),
      size: 8,
      color: k.rgb(160, 170, 190),
    });
  }
}
