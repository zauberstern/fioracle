import type { KAPLAYCtx } from "kaplay";
import { TYPE } from "../ui/type";

export type CascadeNode = {
  id: string;
  weight: number;
  contribution: number;
  color: string;
  chipIndex?: number;
};

export type CascadeRound = {
  order: string[];
  shock: number;
};

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
};

/** Scripted contribution-ordered cascade - no invented adjacency physics. */
export class FireSaleCascade {
  private nodes: CascadeNode[] = [];
  private rounds: CascadeRound[] = [];
  private animRound = 0;
  private timer = 0;
  private readonly roundDur = 0.6;
  private particles: Particle[] = [];
  private fallT = 0;
  caption = "ordered by contribution";
  reducedMotion = false;

  reset(nodes: CascadeNode[]): void {
    this.nodes = [...nodes]
      .filter((n) => n.weight > 0)
      .sort((a, b) => a.contribution - b.contribution)
      .slice(0, 40);
    this.rounds = [];
    this.animRound = 0;
    this.timer = 0;
    this.fallT = 0;
    this.particles = [];
    let shock = 0;
    const order: string[] = [];
    for (const n of this.nodes) {
      if (n.contribution >= 0) continue;
      order.push(n.id);
      shock += Math.abs(n.contribution);
      this.rounds.push({ order: [...order], shock });
      if (this.rounds.length >= 4) break;
    }
    if (this.rounds.length === 0 && this.nodes.length) {
      this.rounds.push({
        order: this.nodes.map((n) => n.id),
        shock: 0,
      });
    }
  }

  get hasRounds(): boolean {
    return this.rounds.length > 0;
  }

  update(dt: number): boolean {
    this.fallT += dt;
    if (!this.reducedMotion) {
      for (const p of this.particles) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.vy += 280 * dt;
        p.life -= dt;
      }
      this.particles = this.particles.filter((p) => p.life > 0).slice(0, 48);
    }
    if (this.animRound >= this.rounds.length) return true;
    this.timer += dt;
    if (this.timer >= this.roundDur) {
      this.timer = 0;
      this.animRound += 1;
      if (!this.reducedMotion) this.burst();
    }
    return this.animRound >= this.rounds.length;
  }

  private burst(): void {
    const round = this.current();
    if (!round) return;
    const n = Math.min(24, 6 + round.order.length * 4);
    for (let i = 0; i < n; i++) {
      this.particles.push({
        x: 120 + Math.random() * 700,
        y: 200 + Math.random() * 80,
        vx: (Math.random() - 0.5) * 180,
        vy: -40 - Math.random() * 120,
        life: 0.35 + Math.random() * 0.35,
        maxLife: 0.7,
      });
    }
  }

  current(): CascadeRound | null {
    if (this.animRound >= this.rounds.length) {
      return this.rounds[this.rounds.length - 1] ?? null;
    }
    return this.rounds[this.animRound] ?? null;
  }

  /** easeInQuad progress 0..1 within current round */
  private fallProgress(): number {
    const t = Math.min(1, this.timer / this.roundDur);
    return t * t;
  }

  draw(k: KAPLAYCtx, x: number, y: number, w: number, h: number): void {
    const round = this.current();
    k.drawText({
      text: `Fire-sale cascade (${this.caption})`,
      pos: k.vec2(x, y),
      font: TYPE.hud.font,
      size: TYPE.hud.size,
      color: k.rgb(232, 228, 217),
    });
    k.drawText({
      text: round ? `shock ${(round.shock * 100).toFixed(2)}%` : "settling",
      pos: k.vec2(x, y + 20),
      font: TYPE.hud.font,
      size: TYPE.hud.size,
      color: k.rgb(213, 94, 0),
    });

    const n = Math.max(this.nodes.length, 1);
    const gap = w / n;
    const prog = this.reducedMotion ? 1 : this.fallProgress();
    const largestLoser = this.nodes[0]?.id;

    this.nodes.forEach((node, i) => {
      const fallen = round?.order.includes(node.id) ?? false;
      const cx = x + gap * i + gap / 2;
      const restY = y + 80;
      const landY = y + h - 48;
      let cy = restY;
      if (fallen) {
        const bounce =
          node.id === largestLoser && prog > 0.85 && !this.reducedMotion
            ? Math.sin((prog - 0.85) * 40) * 6
            : 0;
        cy = restY + (landY - restY) * prog - bounce;
      }
      const [r, g, b] = this.parseColor(node.color);
      const frame = `chip_${(node.chipIndex ?? i) % 8}`;
      try {
        k.drawSprite({
          sprite: frame,
          pos: k.vec2(cx - 28, cy),
          width: 56,
          height: 36,
          color: k.rgb(r, g, b),
          opacity: fallen ? 0.7 : 1,
        });
      } catch {
        k.drawRect({
          pos: k.vec2(cx - 28, cy),
          width: 56,
          height: 28,
          color: k.rgb(r, g, b),
          opacity: fallen ? 0.55 : 1,
        });
      }
      k.drawText({
        text: node.id.slice(0, 8),
        pos: k.vec2(cx - 24, cy + 10),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(10, 10, 18),
      });
    });

    if (!this.reducedMotion) {
      for (const p of this.particles) {
        const a = Math.max(0, p.life / p.maxLife);
        try {
          k.drawSprite({
            sprite: "smoke",
            pos: k.vec2(p.x, p.y),
            width: 12,
            height: 12,
            opacity: a * 0.6,
          });
        } catch {
          k.drawCircle({
            pos: k.vec2(p.x, p.y),
            radius: 3,
            color: k.rgb(180, 180, 180),
            opacity: a * 0.5,
          });
        }
      }
    }
  }

  private parseColor(hex: string): [number, number, number] {
    const h = hex.replace("#", "");
    return [
      parseInt(h.slice(0, 2), 16) || 200,
      parseInt(h.slice(2, 4), 16) || 200,
      parseInt(h.slice(4, 6), 16) || 200,
    ];
  }
}
