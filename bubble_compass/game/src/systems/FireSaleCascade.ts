import type { KAPLAYCtx } from "kaplay";

export interface CascadeNode {
  id: string;
  exposure: number;
  shock: number;
}

export interface CascadeRound {
  round: number;
  nodes: CascadeNode[];
  totalShock: number;
}

/** DebtRank-style contagion rounds for desk crash animation. */
export class FireSaleCascade {
  private rounds: CascadeRound[] = [];
  private animRound = 0;
  private animT = 0;

  reset(nodes: { id: string; exposure: number }[], adjacency: number[][]): CascadeRound[] {
    const n = nodes.length;
    const shock = nodes.map((node) => ({ ...node, shock: 0 }));
    const rounds: CascadeRound[] = [{ round: 0, nodes: shock.map((s) => ({ ...s })), totalShock: 0 }];

    let active = nodes.map((_, i) => i);
    for (let r = 1; r <= 4 && active.length > 0; r++) {
      const next = shock.map((s) => ({ ...s }));
      for (const i of active) {
        const spill = next[i].exposure * 0.35;
        next[i].shock += spill;
        for (let j = 0; j < n; j++) {
          if (i === j) continue;
          next[j].shock += spill * (adjacency[i]?.[j] ?? 0);
        }
      }
      const totalShock = next.reduce((a, b) => a + b.shock, 0);
      rounds.push({ round: r, nodes: next.map((s) => ({ ...s })), totalShock });
      active = next
        .map((s, idx) => ({ s, idx }))
        .filter(({ s }) => s.shock > 0.05)
        .map(({ idx }) => idx);
    }

    this.rounds = rounds;
    this.animRound = 0;
    this.animT = 0;
    return rounds;
  }

  getRounds(): CascadeRound[] {
    return this.rounds;
  }

  tick(dt: number): void {
    if (this.rounds.length === 0) return;
    this.animT += dt;
    if (this.animT >= 0.6) {
      this.animT = 0;
      this.animRound = Math.min(this.animRound + 1, this.rounds.length - 1);
    }
  }

  currentRound(): CascadeRound | null {
    return this.rounds[this.animRound] ?? null;
  }

  draw(k: KAPLAYCtx, originX: number, originY: number): void {
    const round = this.currentRound();
    if (!round) return;
    const maxExp = Math.max(...round.nodes.map((n) => n.exposure), 0.01);
    round.nodes.forEach((node, i) => {
      const radius = 6 + (node.exposure / maxExp) * 10;
      const alpha = Math.min(1, 0.3 + node.shock);
      k.drawCircle({
        pos: k.vec2(originX + 20 + i * 36, originY),
        radius,
        color: k.rgb(255 * alpha, 60, 40 + node.shock * 180),
      });
      k.drawText({
        text: node.id.slice(0, 3),
        pos: k.vec2(originX + 14 + i * 36, originY + 14),
        size: 7,
        color: k.rgb(220, 220, 230),
      });
    });
    k.drawText({
      text: `cascade r${round.round}`,
      pos: k.vec2(originX, originY - 18),
      size: 8,
      color: k.rgb(200, 120, 100),
    });
  }
}
