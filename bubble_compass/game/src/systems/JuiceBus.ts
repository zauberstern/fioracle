import type { AudioBus } from "./AudioBus";

type KaplayJuice = {
  shake: (intensity?: number) => void;
  flash: (color: never, fadeOutTime: number) => unknown;
  rgb: (r: number, g: number, b: number) => never;
  wait: (t: number, cb?: () => void) => unknown;
};

export class JuiceBus {
  reducedMotion = false;
  // Kaplay flash/rgb use Color; keep bind loose so KAPLAYCtx assigns cleanly.
  private k: KaplayJuice | null = null;
  private audio: AudioBus | null = null;

  bind(k: object, audio: AudioBus): void {
    this.k = k as KaplayJuice;
    this.audio = audio;
  }

  setReducedMotion(on: boolean): void {
    this.reducedMotion = on;
  }

  uiClick(): void {
    this.audio?.play("ui_click");
  }

  stamp(): void {
    // Audio only: no full-screen flash (squash + mote live in the desk scene).
    this.audio?.play("ui_confirm");
  }

  chipLand(): void {
    this.audio?.play("ui_click", 0.5);
  }

  positivePrint(): void {
    this.audio?.play("ui_click", 0.4);
  }

  negativePrint(): void {
    this.audio?.play("ui_warn");
    if (this.reducedMotion || !this.k) return;
    this.k.shake(3);
  }

  cascadeHit(): void {
    this.audio?.play("impact");
    if (this.reducedMotion || !this.k) return;
    this.k.flash(this.k.rgb(255, 48, 48), 0.16);
    this.k.shake(8);
  }

  flatDay(): void {
    this.audio?.play("ui_click", 0.25);
  }
}
