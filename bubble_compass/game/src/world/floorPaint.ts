/** Cell → fill/outline for Stillmoor floor paint (no Kaplay import). */

export type RGB = [number, number, number];

export function paintCell(cell: string): { fill: RGB; outline: RGB | null } {
  switch (cell) {
    case "path":
      return { fill: [120, 108, 88], outline: null };
    case "wall":
      return { fill: [92, 83, 70], outline: [176, 141, 79] };
    case "plaza":
    case "district":
      return { fill: [150, 138, 118], outline: [176, 141, 79] };
    case "sundial":
      return { fill: [150, 138, 118], outline: [176, 141, 79] };
    case "bank":
    case "stone":
    case "board":
    case "bard":
    case "nameshop":
      return { fill: [120, 108, 88], outline: [176, 141, 79] };
    case "water":
      return { fill: [92, 83, 70], outline: null };
    case "grass":
    default:
      return { fill: [74, 92, 58], outline: null };
  }
}
