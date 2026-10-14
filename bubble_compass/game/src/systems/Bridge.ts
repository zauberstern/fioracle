/** Parent ↔ iframe postMessage contract (same-origin). */

export type ParentToGame =
  | { type: "asOf"; date: string }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "mute"; muted: boolean }
  | { type: "reducedMotion"; on: boolean }
  | { type: "episode"; id: string };

export type GameToParent =
  | { type: "boot" }
  | { type: "ready" }
  | { type: "turnCommitted"; asOf: string; weights: Record<string, number>; score: number }
  | { type: "requestFocus" }
  | { type: "error"; message: string };

type Handlers = {
  onAsOf?: (date: string) => void;
  onPause?: () => void;
  onResume?: () => void;
  onMute?: (muted: boolean) => void;
  onReducedMotion?: (on: boolean) => void;
  onEpisode?: (id: string) => void;
};

export class Bridge {
  private handlers: Handlers = {};
  private listening = false;
  /** Origin of the first accepted parent message. Replies go there. */
  private replyOrigin: string | null = null;

  setHandlers(h: Handlers): void {
    this.handlers = h;
  }

  start(): void {
    if (this.listening) return;
    this.listening = true;
    window.addEventListener("message", this.onMessage);
  }

  stop(): void {
    window.removeEventListener("message", this.onMessage);
    this.listening = false;
  }

  /** Parent origin when embedded; own origin when standalone. */
  private parentOrigin(): string {
    try {
      if (document.referrer) {
        return new URL(document.referrer).origin;
      }
    } catch {
      /* ignore */
    }
    return window.location.origin;
  }

  post(msg: GameToParent): void {
    try {
      const target =
        this.replyOrigin ??
        (import.meta.env.DEV ? "*" : this.parentOrigin());
      window.parent?.postMessage(msg, target);
    } catch {
      /* standalone */
    }
  }

  private onMessage = (ev: MessageEvent): void => {
    // Same-origin required in prod; DEV allows parent on another Vite port.
    const same =
      ev.origin === window.location.origin ||
      ev.origin === "null" ||
      (import.meta.env.DEV && typeof ev.data?.type === "string");
    if (!same) return;
    if (ev.origin && ev.origin !== "null") this.replyOrigin = ev.origin;
    if (typeof ev.data?.type !== "string") return;
    const data = ev.data as ParentToGame;
    if (!data || typeof data !== "object" || !("type" in data)) return;
    switch (data.type) {
      case "asOf":
        this.handlers.onAsOf?.(data.date);
        break;
      case "pause":
        this.handlers.onPause?.();
        break;
      case "resume":
        this.handlers.onResume?.();
        break;
      case "mute":
        this.handlers.onMute?.(Boolean(data.muted));
        break;
      case "reducedMotion":
        this.handlers.onReducedMotion?.(Boolean(data.on));
        break;
      case "episode":
        this.handlers.onEpisode?.(data.id);
        break;
      default:
        break;
    }
  };
}
