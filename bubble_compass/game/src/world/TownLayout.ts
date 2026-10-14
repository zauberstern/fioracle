/** Stillmoor districts, stones, and scenery. Mass is weight; Book is the only worn item. */

import { EPISODES } from "../../../shared/episodes";
import { MAP_H, MAP_W } from "../ui/layout";

export type CellKind =
  | "grass"
  | "path"
  | "wall"
  | "plaza"
  | "district"
  | "stone"
  | "sundial"
  | "bank"
  | "stall"
  | "board"
  | "bard"
  | "nameshop"
  | "water";

export type DistrictDef = {
  sleeveId: string;
  place: string;
  verb: string;
  tool: string;
  /** Map cell (tile coords). */
  tx: number;
  ty: number;
};

export type StoneDef = {
  episodeId: string;
  title: string;
  date: string;
  tx: number;
  ty: number;
};

export const DISTRICTS: DistrictDef[] = [
  {
    sleeveId: "SP500_TOTAL_RETURN",
    place: "Standing Grove",
    verb: "Chop",
    tool: "tool_axe",
    tx: 16,
    ty: 4,
  },
  {
    sleeveId: "BBG_US_HIGH_YIELD_TOTAL_RETURN",
    place: "Brine Fen",
    verb: "Fish",
    tool: "tool_hook",
    tx: 26,
    ty: 8,
  },
  {
    sleeveId: "BBG_US_CORPORATE_TOTAL_RETURN",
    place: "Anvil Row",
    verb: "Smith",
    tool: "tool_hammer",
    tx: 26,
    ty: 16,
  },
  {
    sleeveId: "BBG_US_TREASURY_TOTAL_RETURN",
    place: "White Steps",
    verb: "Pray",
    tool: "tool_kneeler",
    tx: 16,
    ty: 20,
  },
  {
    sleeveId: "GOLD_TOTAL_RETURN",
    place: "Hard Ridge",
    verb: "Mine",
    tool: "tool_pick",
    tx: 6,
    ty: 16,
  },
  {
    sleeveId: "US_CASH_RETURN",
    place: "Stillvault",
    verb: "Bank",
    tool: "tool_chest",
    tx: 6,
    ty: 8,
  },
  {
    sleeveId: "CDX_HY_5Y_TOTAL_RETURN",
    place: "Short Gate",
    verb: "Hex",
    tool: "tool_ticks",
    tx: 10,
    ty: 4,
  },
  {
    sleeveId: "CDX_IG_5Y_TOTAL_RETURN",
    place: "Quiet Circle",
    verb: "Ward",
    tool: "tool_shield",
    tx: 22,
    ty: 4,
  },
];

/** Stillmoor quest-stone titles (plan names; dates from EPISODES). */
const STONE_TITLES: Record<string, string> = {
  dotcom: "The Opening",
  gfc: "The House that Fell",
  covid: "The White Day",
  tightening: "The Tight Year",
  banks23: "The Vault Run",
};

const STONE_CELLS: [number, number][] = [
  [12, 10],
  [20, 10],
  [12, 14],
  [20, 14],
  [16, 9],
];

export function buildStones(): StoneDef[] {
  return EPISODES.map((ep, i) => {
    const [tx, ty] = STONE_CELLS[i] ?? [16, 12];
    return {
      episodeId: ep.id,
      title: STONE_TITLES[ep.id] ?? ep.title,
      date: ep.date,
      tx,
      ty,
    };
  });
}

export type SceneryDef = {
  tx: number;
  ty: number;
  frame: string;
  line?: string;
};

const LAMP = "A lamp by the path. It does not change the score.";
const BENCH = "A bench off the road. The stamp is the sundial.";
const PLANTER = "A planter. The weight sits on the book, not here.";
const BIN = "A bin. It is not a book.";
const AWNING = "An awning. Change the weight on the book beneath it, then stamp.";
const HEDGE = "A hedge line. The books are on the districts.";
const SIGN = "A sign. It names the side of town. The weight is on the book.";
const CONE = "A cone at the gate. The crash gate is the one in the ledger.";
const COLUMN = "A column. The stretch stone is the marked stone by the sundial.";
const CART = "A cart left by the road. It does not move, and it does not score.";

/** Townsfolk and dressing on open grass, beside the roads. Not on the sundial. */
export const SCENERY: SceneryDef[] = [
  { tx: 15, ty: 5, frame: "folk_grove" },
  { tx: 14, ty: 5, frame: "prop_lamp", line: LAMP },
  { tx: 17, ty: 5, frame: "prop_planter", line: PLANTER },
  { tx: 25, ty: 7, frame: "folk_fen" },
  { tx: 24, ty: 7, frame: "prop_bench", line: BENCH },
  { tx: 25, ty: 15, frame: "folk_anvil" },
  { tx: 24, ty: 15, frame: "prop_bin", line: BIN },
  { tx: 27, ty: 15, frame: "prop_awning", line: AWNING },
  { tx: 15, ty: 19, frame: "folk_steps" },
  { tx: 17, ty: 19, frame: "prop_hedge", line: HEDGE },
  { tx: 7, ty: 15, frame: "folk_ridge" },
  { tx: 5, ty: 15, frame: "prop_pot", line: PLANTER },
  { tx: 8, ty: 15, frame: "prop_sign_b", line: SIGN },
  { tx: 4, ty: 6, frame: "prop_column", line: COLUMN },
  { tx: 5, ty: 7, frame: "prop_lamp", line: LAMP },
  { tx: 5, ty: 9, frame: "prop_bin", line: BIN },
  { tx: 11, ty: 5, frame: "prop_sign", line: SIGN },
  { tx: 12, ty: 3, frame: "prop_cone", line: CONE },
  { tx: 21, ty: 5, frame: "prop_hedge_short", line: HEDGE },
  { tx: 22, ty: 5, frame: "prop_hedge_short", line: HEDGE },
  { tx: 23, ty: 5, frame: "prop_fence", line: HEDGE },
  { tx: 23, ty: 6, frame: "prop_fence", line: HEDGE },
  { tx: 22, ty: 7, frame: "prop_cart", line: CART },
  { tx: 8, ty: 14, frame: "prop_fence", line: HEDGE },
  { tx: 24, ty: 14, frame: "prop_fence", line: HEDGE },
  { tx: 10, ty: 21, frame: "prop_fence", line: HEDGE },
  { tx: 22, ty: 21, frame: "prop_fence", line: HEDGE },
  { tx: 12, ty: 6, frame: "prop_barrel", line: BIN },
  { tx: 20, ty: 6, frame: "prop_barrel", line: BIN },
  { tx: 12, ty: 18, frame: "prop_barrel", line: BIN },
  { tx: 20, ty: 18, frame: "prop_barrel", line: BIN },
];

export type StillmoorLayout = {
  cells: CellKind[][];
  solid: boolean[][];
  districts: DistrictDef[];
  stones: StoneDef[];
  scenery: SceneryDef[];
  sundial: { tx: number; ty: number };
  stretchStone: { tx: number; ty: number };
  board: { tx: number; ty: number };
  bard: { tx: number; ty: number };
  nameshop: { tx: number; ty: number };
  spawn: { tx: number; ty: number };
};

function blank(kind: CellKind): CellKind[][] {
  return Array.from({ length: MAP_H }, () =>
    Array.from({ length: MAP_W }, () => kind)
  );
}

export function buildStillmoor(): StillmoorLayout {
  const cells = blank("grass");
  const solid = Array.from({ length: MAP_H }, () =>
    Array.from({ length: MAP_W }, () => false)
  );

  // Outer walls
  for (let x = 0; x < MAP_W; x++) {
    cells[0][x] = "wall";
    cells[MAP_H - 1][x] = "wall";
    solid[0][x] = true;
    solid[MAP_H - 1][x] = true;
  }
  for (let y = 0; y < MAP_H; y++) {
    cells[y][0] = "wall";
    cells[y][MAP_W - 1] = "wall";
    solid[y][0] = true;
    solid[y][MAP_W - 1] = true;
  }

  // Plaza ring around sundial
  const sundial = { tx: 16, ty: 12 };
  for (let dy = -3; dy <= 3; dy++) {
    for (let dx = -3; dx <= 3; dx++) {
      const x = sundial.tx + dx;
      const y = sundial.ty + dy;
      if (x > 0 && x < MAP_W - 1 && y > 0 && y < MAP_H - 1) {
        cells[y][x] = "plaza";
      }
    }
  }

  // Paths clockwise (sundial cell restored after)
  for (let x = 6; x <= 26; x++) {
    cells[8][x] = "path";
    cells[16][x] = "path";
  }
  for (let y = 4; y <= 20; y++) {
    cells[y][6] = "path";
    cells[y][26] = "path";
    cells[y][16] = "path";
  }
  cells[sundial.ty][sundial.tx] = "sundial";

  const pool = [
    [27, 9],
    [28, 9],
    [27, 10],
    [28, 10],
  ] as const;
  for (const [x, y] of pool) {
    cells[y][x] = "water";
    solid[y][x] = true;
  }

  const districts = DISTRICTS.map((d) => ({ ...d }));
  for (const d of districts) {
    cells[d.ty][d.tx] = d.sleeveId === "US_CASH_RETURN" ? "bank" : "district";
  }

  const stones = buildStones();
  for (const s of stones) {
    if (s.tx === sundial.tx && s.ty === sundial.ty) continue;
    cells[s.ty][s.tx] = "stone";
  }

  const stretchStone = { tx: 14, ty: 11 };
  const board = { tx: 18, ty: 11 };
  const bard = { tx: 14, ty: 13 };
  const nameshop = { tx: 18, ty: 13 };
  cells[stretchStone.ty][stretchStone.tx] = "stone";
  cells[board.ty][board.tx] = "board";
  cells[bard.ty][bard.tx] = "bard";
  cells[nameshop.ty][nameshop.tx] = "nameshop";
  solid[bard.ty][bard.tx] = true;
  solid[nameshop.ty][nameshop.tx] = true;

  const scenery = SCENERY.filter((s) => cells[s.ty]?.[s.tx] === "grass");
  for (const s of scenery) {
    solid[s.ty][s.tx] = true;
  }

  return {
    cells,
    solid,
    districts,
    stones,
    scenery,
    sundial,
    stretchStone,
    board,
    bard,
    nameshop,
    spawn: { tx: sundial.tx, ty: sundial.ty + 1 },
  };
}
