/** Typed atlas frame names for desk.png / town.png */

export const SPRITE_FRAMES = [
  "panel",
  "panel_hot",
  "btn",
  "btn_amber",
  "chip_0",
  "chip_1",
  "chip_2",
  "chip_3",
  "chip_4",
  "chip_5",
  "chip_6",
  "chip_7",
  "icon_warn",
  "icon_pause",
  "icon_lock",
  "icon_heat",
  "icon_stretch",
  "particle",
  "smoke",
  "crack",
  "meter_bg",
  "meter_fill",
  "vignette",
  "key_space",
  "key_enter",
  "arrow_up",
  "arrow_down",
  "focus_ring",
  "blank",
] as const;

export const TOWN_FRAMES = [
  "tile_grass",
  "tile_path",
  "tile_wall",
  "tile_plaza",
  "prop_stone",
  "prop_bank",
  "prop_sundial",
  "prop_stall",
  "player_n",
  "player_s",
  "player_e",
  "player_w",
  "player_n_1",
  "player_s_1",
  "player_e_1",
  "player_w_1",
  "inv_slot",
  "orb_ring",
  "btn_stone",
  "chat_panel",
  "tool_axe",
  "tool_hook",
  "tool_hammer",
  "tool_kneeler",
  "tool_pick",
  "tool_chest",
  "tool_ticks",
  "tool_shield",
  "fx_spark",
  "fx_star",
  "ui_corner_tl",
  "ui_corner_tr",
  "ui_corner_bl",
  "ui_corner_br",
  "folk_grove",
  "folk_fen",
  "folk_anvil",
  "folk_steps",
  "folk_ridge",
  "ground_grass",
  "ground_path_h",
  "ground_path_v",
  "ground_path_x",
  "ground_plaza",
  "ground_water",
  "prop_lamp",
  "prop_bench",
  "prop_planter",
  "prop_bin",
  "prop_awning",
  "prop_hedge",
  "prop_hedge_short",
  "prop_pot",
  "prop_sign",
  "prop_sign_b",
  "prop_cone",
  "prop_fence",
  "prop_cart",
  "prop_column",
  "prop_barrel",
] as const;

export type SpriteName = (typeof SPRITE_FRAMES)[number];
export type TownSpriteName = (typeof TOWN_FRAMES)[number];

export const SOUND_NAMES = ["ui_click", "ui_confirm", "ui_warn", "impact"] as const;
export type SoundName = (typeof SOUND_NAMES)[number];

export function loadDeskAssets(k: {
  loadRoot: (path: string) => void;
  loadSpriteAtlas: (img: string, atlas: string | Record<string, unknown>) => void;
  loadSound: (name: string, path: string) => void;
  loadFont?: (name: string, path: string) => void;
}): Promise<void> {
  const base = import.meta.env.BASE_URL || "/";
  const root = base.endsWith("/") ? base : `${base}/`;
  k.loadRoot(root);

  // Kaplay prefixes only the PNG. Fetch JSON with the same root, then queue the PNG
  // before anyone listens for onLoad. An empty queue already reports progress 1.
  async function atlas(name: "town" | "desk") {
    const res = await fetch(`${root}atlases/${name}.kaplay.json`);
    if (!res.ok) throw new Error(`${name} atlas ${res.status}`);
    const json = (await res.json()) as Record<string, unknown>;
    k.loadSpriteAtlas(`atlases/${name}.png`, json);
  }
  const queued = Promise.all([atlas("town"), atlas("desk")]).then(() => undefined);

  for (const name of SOUND_NAMES) {
    k.loadSound(name, `audio/${name}.ogg`);
  }
  k.loadFont?.("PlexMono", "fonts/IBMPlexMono-Regular.woff2");
  k.loadFont?.("PlexSans", "fonts/IBMPlexSans-Regular.woff2");
  return queued;
}
