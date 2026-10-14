export type ChatTone = "examine" | "tape" | "alert" | "system";

export type ChatLine = { text: string; tone: ChatTone };

const MAX_LINES = 48;
const VISIBLE = 10;

export class Chatbox {
  private lines: ChatLine[] = [];
  artMissing = false;

  push(text: string, tone: ChatTone = "tape"): void {
    this.lines.push({ text, tone });
    if (this.lines.length > MAX_LINES) {
      this.lines.splice(0, this.lines.length - MAX_LINES);
    }
  }

  visible(): ChatLine[] {
    return this.lines.slice(-VISIBLE);
  }

  markArtMissing(): void {
    if (this.artMissing) return;
    this.artMissing = true;
    this.push("art missing", "alert");
  }
}
