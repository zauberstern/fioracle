import type { SoundName } from "../assets/manifest";

type KaplayPlay = {
  play: (name: string, opts?: { volume?: number; loop?: boolean }) => unknown;
  volume: (v?: number) => number;
};

export class AudioBus {
  sfx = 0.85;
  music = 0.55;
  muted = true;
  unlocked = false;
  private k: KaplayPlay | null = null;

  bind(k: KaplayPlay): void {
    this.k = k;
  }

  unlock(): void {
    this.unlocked = true;
    this.muted = false;
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
  }

  play(name: SoundName, volumeScale = 1): void {
    if (!this.k || this.muted || !this.unlocked) return;
    const master = this.k.volume();
    this.k.play(name, { volume: master * this.sfx * volumeScale });
  }
}
