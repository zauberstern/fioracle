import type { KAPLAYCtx } from "kaplay";
import { plainDate } from "../../../shared/plainDate";
import universe from "../data/universe.json";
import { Sleeve } from "../entities/Sleeve";
import { MarketTicker } from "../entities/MarketTicker";
import { persistSession, type GameState } from "../gameState";
import type { TurnScoreBreakdown } from "../systems/ScoreKeeper";
import { decideStampPrint } from "../systems/stampPrint";
import {
  CANVAS,
  CHAT,
  MAP_H,
  MAP_W,
  ORB_CLUSTER,
  PACK,
  STAMP,
  TILE_DRAW,
  VIEWPORT,
  VIEWPORT_INNER,
  hitTest,
  slotRect,
} from "../ui/layout";
import { Chatbox } from "../ui/Chatbox";
import { RULES, STAND_IN } from "../ui/tutorialCopy";
import { textBlockHeight, TYPE } from "../ui/type";
import {
  examineBard,
  examineBoard,
  examineBook,
  examineDistrict,
  examineEmptySlot,
  examineFlatDay,
  examineGate,
  examineNameShop,
  examineStone,
  examineStretchStone,
  examineSundial,
} from "../ui/Examine";
import {
  WELL_BRASS,
  WELL_PARCHMENT,
  WELL_STONE,
  drawWell,
} from "../ui/frame";
import { weightsToQty } from "../ui/InventoryPanel";
import { drawMinimap, minimapTileAt } from "../ui/MinimapOrb";
import { paintCell } from "../world/floorPaint";
import { Player } from "../world/Player";
import { shortestPath, type Tile } from "../world/pathfind";
import { TileMap } from "../world/TileMap";
import { DISTRICTS } from "../world/TownLayout";

type DeskPhase = "idle" | "targeting" | "locked" | "resolving";

type ContextMenu = {
  x: number;
  y: number;
  title: string;
  options: { label: string; action: () => void }[];
} | null;

function trySprite(
  k: KAPLAYCtx,
  sprite: string,
  pos: { x: number; y: number },
  w: number,
  h: number
): boolean {
  const getter = (k as { getSprite?: (name: string) => { data?: unknown } | null }).getSprite;
  if (typeof getter === "function") {
    const spr = getter.call(k, sprite);
    if (!spr?.data) return false;
  }
  try {
    k.drawSprite({
      sprite,
      pos: k.vec2(pos.x, pos.y),
      width: w,
      height: h,
    });
    return true;
  } catch {
    return false;
  }
}

export function registerDeskScene(k: KAPLAYCtx, gs: GameState): void {
  k.scene("desk", () => {
    const ticker = new MarketTicker();
    const sleeves = Sleeve.catalog();
    const sleeveIds = sleeves.map((s) => s.def.id);
    const map = new TileMap();
    const player = new Player(map.layout.spawn.tx, map.layout.spawn.ty);
    map.clampCamera(player.tx, player.ty);
    const chat = new Chatbox();
    chat.push(STAND_IN, "system");
    for (const rule of RULES) chat.push(rule, "system");

    const pushRules = () => {
      for (const rule of RULES) chat.push(rule, "system");
    };

    let phase: DeskPhase = "idle";
    let lastBreakdown: TurnScoreBreakdown | null = gs.lastBreakdown;
    let stampScale = 1;
    let printPopup: {
      text: string;
      y: number;
      life: number;
      up: boolean;
    } | null = null;
    let inputBufferUntil = 0;
    let mouseover = "Walk here";
    let menu: ContextMenu = null;
    let atlasOk = true;
    let flashDistrict: { tx: number; ty: number; life: number } | null = null;
    let showHowToWalk = true;

    const persist = () => persistSession();

    const commitSync = () => {
      if (phase !== "idle" && phase !== "targeting") return;
      if (!gs.tape.hasTape || gs.paused) return;
      if (k.time() < inputBufferUntil) return;

      phase = "locked";
      gs.ignoreInboundAsOf = true;
      inputBufferUntil = k.time() + 0.15;
      stampScale = 0.86;
      gs.juice.stamp();
      k.wait(0.06, () => {
        stampScale = 1.12;
      });
      k.wait(0.2, () => {
        stampScale = 1;
        phase = "resolving";

        const rawReturns: Record<string, number> = {};
        for (const s of sleeves) {
          rawReturns[s.def.id] = gs.tape.sleeveDailyReturn(s.def.id);
        }
        const benchRaw = gs.tape.sleeveDailyReturn(universe.benchmark);
        const decision = decideStampPrint(
          sleeves.map((s) => s.def.id),
          rawReturns,
          benchRaw
        );

        if (decision.kind === "no_print") {
          gs.juice.flatDay();
          chat.push("No print on this row, so the day does not score.", "tape");
          // Advance so a hole cannot trap the player; do not score or album.
          const atEnd =
            gs.sessionTurns >= gs.maxTurnsPerSession || !gs.tape.advance();
          gs.bridge.post({
            type: "turnCommitted",
            asOf: gs.tape.currentAsOf(),
            weights: gs.portfolio.weights,
            score: gs.lastTurnScore,
          });
          if (atEnd) {
            phase = "idle";
            gs.ignoreInboundAsOf = false;
            k.go("debrief");
            return;
          }
          phase = "idle";
          gs.ignoreInboundAsOf = false;
          return;
        }

        const { returns, benchRet } = decision;
        lastBreakdown = gs.score.scoreTurn(
          gs.portfolio.weights,
          returns,
          benchRet
        );
        gs.lastBreakdown = lastBreakdown;
        gs.lastTurnScore = lastBreakdown.total;
        gs.sessionTurns += 1;
        const stampedAsOf = gs.tape.currentAsOf();
        gs.album.record({
          asOf: stampedAsOf,
          score: lastBreakdown.total,
          portReturn: lastBreakdown.portfolioReturn,
        });
        persist();
        chat.push(
          `Album holds ${gs.album.count()} stamps. Latest is ${plainDate(stampedAsOf)}.`,
          "system"
        );

        const absRet = Math.abs(lastBreakdown.portfolioReturn);
        if (absRet < 1e-8) {
          gs.juice.flatDay();
          chat.push(examineFlatDay(), "tape");
        } else if (lastBreakdown.portfolioReturn > 0) {
          gs.juice.positivePrint();
          if (!gs.juice.reducedMotion) {
            printPopup = {
              text: `\u25B2 +${(lastBreakdown.portfolioReturn * 100).toFixed(2)}%`,
              y: 0,
              life: 0.4,
              up: true,
            };
          }
          chat.push(
            `The book prints ${(lastBreakdown.portfolioReturn * 100).toFixed(2)}%.`,
            "tape"
          );
          let bestId = "";
          let bestAbs = 0;
          for (const s of sleeves) {
            const c = Math.abs(
              (gs.portfolio.weights[s.def.id] ?? 0) * (returns[s.def.id] ?? 0)
            );
            if (c > bestAbs) {
              bestAbs = c;
              bestId = s.def.id;
            }
          }
          const d = DISTRICTS.find((x) => x.sleeveId === bestId);
          if (d) flashDistrict = { tx: d.tx, ty: d.ty, life: 0.45 };
        } else {
          gs.juice.negativePrint();
          if (!gs.juice.reducedMotion) {
            printPopup = {
              text: `\u25BC ${(lastBreakdown.portfolioReturn * 100).toFixed(2)}%`,
              y: 0,
              life: 0.4,
              up: false,
            };
          }
          chat.push(
            `The book prints ${(lastBreakdown.portfolioReturn * 100).toFixed(2)}%.`,
            "tape"
          );
          let bestId = "";
          let bestAbs = 0;
          for (const s of sleeves) {
            const c = Math.abs(
              (gs.portfolio.weights[s.def.id] ?? 0) * (returns[s.def.id] ?? 0)
            );
            if (c > bestAbs) {
              bestAbs = c;
              bestId = s.def.id;
            }
          }
          const d = DISTRICTS.find((x) => x.sleeveId === bestId);
          if (d) flashDistrict = { tx: d.tx, ty: d.ty, life: 0.45 };
        }

        const gate = gs.tape.shouldCrash(lastBreakdown.portfolioReturn);
        if (gate.triggered) {
          gs.crashTriggered = true;
          gs.crashReason = gate.reason;
          persist();
          chat.push(examineGate(gate.reason), "alert");
          // Keep ignoreInboundAsOf until CrashScene.leave advances + posts.
          phase = "idle";
          k.go("crash", { breakdown: lastBreakdown, reason: gate.reason });
          return;
        }

        const atEnd =
          gs.sessionTurns >= gs.maxTurnsPerSession || !gs.tape.advance();
        // Post after advance so the parent scrubber matches the desk tip.
        gs.bridge.post({
          type: "turnCommitted",
          asOf: gs.tape.currentAsOf(),
          weights: gs.portfolio.weights,
          score: lastBreakdown.total,
        });
        if (atEnd) {
          phase = "idle";
          gs.ignoreInboundAsOf = false;
          k.go("debrief");
          return;
        }
        phase = "idle";
        gs.ignoreInboundAsOf = false;
      });
    };

    const bumpSleeve = (idx: number, delta: number) => {
      if (gs.paused || phase === "locked" || phase === "resolving") return;
      gs.portfolio.selectIndex(idx);
      gs.portfolio.bumpSelected(delta);
      phase = "targeting";
      gs.juice.uiClick();
    };

    const examineAtTile = (tx: number, ty: number) => {
      const hud = gs.tape.benchmarkHud();
      const asOf = gs.tape.currentAsOf();
      const layout = map.layout;
      if (layout.cells[ty]?.[tx] === "water") {
        chat.push("Still water. Walk around it. It does not score.", "examine");
        return;
      }
      const dressed = layout.scenery.find((s) => s.tx === tx && s.ty === ty);
      if (dressed?.line) {
        chat.push(dressed.line, "examine");
        return;
      }
      if (tx === layout.sundial.tx && ty === layout.sundial.ty) {
        chat.push(examineSundial(asOf), "examine");
        return;
      }
      if (tx === layout.stretchStone.tx && ty === layout.stretchStone.ty) {
        chat.push(examineStretchStone(hud), "examine");
        return;
      }
      if (tx === layout.board.tx && ty === layout.board.ty) {
        chat.push(examineBoard(hud), "examine");
        return;
      }
      if (tx === layout.bard.tx && ty === layout.bard.ty) {
        chat.push(examineBard(), "examine");
        return;
      }
      if (tx === layout.nameshop.tx && ty === layout.nameshop.ty) {
        chat.push(examineNameShop(), "examine");
        return;
      }
      const stone = layout.stones.find((s) => s.tx === tx && s.ty === ty);
      if (stone) {
        chat.push(examineStone(stone), "examine");
        return;
      }
      const dist = layout.districts.find((d) => d.tx === tx && d.ty === ty);
      if (dist) {
        chat.push(
          examineDistrict(
            dist,
            gs.portfolio.weights[dist.sleeveId] ?? 0,
            gs.tape.sleeveDailyReturn(dist.sleeveId)
          ),
          "examine"
        );
        return;
      }
      chat.push(examineEmptySlot(), "examine");
    };

    let path: Tile[] = [];
    let dest: Tile | null = null;
    let usedDest = false;
    let pendingStep: { dx: number; dy: number } | null = null;
    let artMissSent = false;

    const isInteractive = (tx: number, ty: number): boolean => {
      const layout = map.layout;
      if (tx === layout.sundial.tx && ty === layout.sundial.ty) return true;
      if (layout.stones.some((s) => s.tx === tx && s.ty === ty)) return true;
      if (layout.districts.some((d) => d.tx === tx && d.ty === ty)) return true;
      return false;
    };

    const howToCard = () => {
      const w = VIEWPORT_INNER.w - 48;
      const inner = w - 32;
      let h = 48;
      const rows = RULES.map((rule) => {
        const block = textBlockHeight(k, rule, TYPE.chat.font, TYPE.chat.size, inner);
        const y = h;
        h += block;
        return { rule, y };
      });
      return {
        x: VIEWPORT_INNER.x + 24,
        y: VIEWPORT_INNER.y + 40,
        w,
        h: h + 12,
        rows,
      };
    };

    const queueWalk = (tx: number, ty: number) => {
      showHowToWalk = false;
      usedDest = false;
      dest = { tx, ty };
      const from: Tile = { tx: player.tx, ty: player.ty };
      const solid = (x: number, y: number) => map.isSolid(x, y);

      if (isInteractive(tx, ty)) {
        if (player.adjacentTo(tx, ty)) {
          path = [];
          return;
        }
        const candidates: Tile[] = [
          { tx, ty: ty - 1 },
          { tx: tx + 1, ty },
          { tx, ty: ty + 1 },
          { tx: tx - 1, ty },
        ].filter((n) => !solid(n.tx, n.ty));
        let best: Tile[] | null = null;
        for (const n of candidates) {
          const p = shortestPath(solid, from, n, MAP_W, MAP_H);
          if (p === null) continue;
          if (best === null || p.length < best.length) best = p;
        }
        if (best === null) {
          chat.push("You can't walk there.", "system");
          dest = null;
          path = [];
          return;
        }
        path = best;
        return;
      }

      const p = shortestPath(solid, from, { tx, ty }, MAP_W, MAP_H);
      if (p === null) {
        chat.push("You can't walk there.", "system");
        dest = null;
        path = [];
        return;
      }
      path = p;
    };

    const useTile = (tx: number, ty: number) => {
      if (phase === "locked" || phase === "resolving") return;
      const layout = map.layout;
      if (tx === layout.sundial.tx && ty === layout.sundial.ty) {
        commitSync();
        return;
      }
      const stone = layout.stones.find((s) => s.tx === tx && s.ty === ty);
      if (stone) {
        gs.tape.jumpToDate(stone.date);
        const snapped = gs.tape.currentAsOf();
        gs.town.touchStone(stone.date);
        chat.push(
          `The book turns to ${stone.title} (${plainDate(snapped)}).`,
          "tape"
        );
        return;
      }
      const dist = layout.districts.find((d) => d.tx === tx && d.ty === ty);
      if (dist) {
        const idx = sleeveIds.indexOf(dist.sleeveId);
        if (idx >= 0) bumpSleeve(idx, 0.05);
      }
    };

    gs.bridge.setHandlers({
      onAsOf: (date) => {
        if (gs.ignoreInboundAsOf) return;
        if (phase === "locked" || phase === "resolving") return;
        gs.parentAsOf = date;
        gs.tape.jumpToDate(date);
      },
      onMute: (m) => gs.audio.setMuted(m),
      onReducedMotion: (on) => gs.juice.setReducedMotion(on),
      onPause: () => {
        gs.paused = true;
      },
      onResume: () => {
        gs.paused = false;
      },
    });

    k.onUpdate(() => {
      const vis = player.visualTile();
      map.clampCamera(vis.x, vis.y);
      if (!gs.paused) ticker.tick(k.dt());
      // District visit: once per enter (edge on sleeve id).
      const here = map.layout.districts.find(
        (d) => d.tx === player.tx && d.ty === player.ty
      );
      gs.town.enterDistrict(here?.sleeveId ?? null);
      if (printPopup) {
        printPopup.y += k.dt() * 28;
        printPopup.life -= k.dt();
        if (printPopup.life <= 0) printPopup = null;
      }
      if (flashDistrict) {
        flashDistrict.life -= k.dt();
        if (flashDistrict.life <= 0) flashDistrict = null;
      }

      const canAct =
        !gs.paused &&
        (phase === "idle" || phase === "targeting") &&
        player.readyToHop();

      // One buffered key. A wall bump must not cancel a click path.
      if (canAct && pendingStep) {
        const step = pendingStep;
        pendingStep = null;
        if (player.tryMove(map, step.dx, step.dy)) {
          path = [];
          dest = null;
          usedDest = true;
          gs.audio.play("ui_click", 0.3);
        }
      }

      if (
        path.length > 0 &&
        canAct &&
        !(
          k.isKeyDown("left") ||
          k.isKeyDown("right") ||
          k.isKeyDown("up") ||
          k.isKeyDown("down") ||
          k.isKeyDown("a") ||
          k.isKeyDown("d") ||
          k.isKeyDown("w") ||
          k.isKeyDown("s")
        )
      ) {
        const next = path[0]!;
        const dx = Math.sign(next.tx - player.tx);
        const dy = Math.sign(next.ty - player.ty);
        if (Math.abs(dx) + Math.abs(dy) !== 1) {
          path = [];
          dest = null;
        } else if (player.tryMove(map, dx, dy)) {
          path.shift();
          gs.audio.play("ui_click", 0.3);
        } else {
          path = [];
          dest = null;
        }
      }

      if (
        path.length === 0 &&
        dest &&
        !usedDest &&
        !gs.paused &&
        (phase === "idle" || phase === "targeting") &&
        isInteractive(dest.tx, dest.ty) &&
        player.adjacentTo(dest.tx, dest.ty)
      ) {
        useTile(dest.tx, dest.ty);
        usedDest = true;
        dest = null;
      }

      if (
        path.length === 0 &&
        dest &&
        player.tx === dest.tx &&
        player.ty === dest.ty &&
        !isInteractive(dest.tx, dest.ty)
      ) {
        dest = null;
      }
    });

    k.onDraw(() => {
      const W = CANVAS.w;
      const H = CANVAS.h;
      // Opaque stone chrome
      k.drawRect({
        pos: k.vec2(0, 0),
        width: W,
        height: H,
        color: k.rgb(58, 52, 44),
      });

      const hud = gs.tape.benchmarkHud();
      const qty = weightsToQty(gs.portfolio.weights, sleeveIds);

      // Viewport stone frame
      k.drawRect({
        pos: k.vec2(VIEWPORT.x, VIEWPORT.y),
        width: VIEWPORT.w,
        height: VIEWPORT.h,
        color: k.rgb(42, 36, 28),
      });
      k.drawRect({
        pos: k.vec2(VIEWPORT_INNER.x, VIEWPORT_INNER.y),
        width: VIEWPORT_INNER.w,
        height: VIEWPORT_INNER.h,
        color: k.rgb(58, 52, 44),
      });

      // Town tiles: paint floor first; sprites are optional.
      const viewTilesX = Math.floor(VIEWPORT_INNER.w / TILE_DRAW);
      const viewTilesY = Math.floor(VIEWPORT_INNER.h / TILE_DRAW);
      let drewAny = false;
      let missAny = false;
      for (let ty = map.camY; ty < map.camY + viewTilesY; ty++) {
        for (let tx = map.camX; tx < map.camX + viewTilesX; tx++) {
          if (tx < 0 || ty < 0) continue;
          const cell = map.layout.cells[ty]?.[tx];
          if (!cell) continue;
          const pos = map.screenOf(tx, ty);
          const onH = (ty === 8 || ty === 16) && tx >= 6 && tx <= 26;
          const onV = (tx === 6 || tx === 16 || tx === 26) && ty >= 4 && ty <= 20;
          let ground: string | null = null;
          if (cell === "wall") {
            const paint = paintCell(cell);
            k.drawRect({
              pos: k.vec2(pos.x, pos.y),
              width: TILE_DRAW,
              height: TILE_DRAW,
              color: k.rgb(...paint.fill),
            });
            if (paint.outline) {
              k.drawRect({
                pos: k.vec2(pos.x, pos.y),
                width: TILE_DRAW,
                height: TILE_DRAW,
                fill: false,
                outline: { width: 2, color: k.rgb(...paint.outline) },
              });
            }
          } else if (cell === "water") {
            ground = "ground_water";
          } else if (cell === "grass") {
            ground = "ground_grass";
          } else if (onH || onV || cell === "path") {
            ground = onH && onV ? "ground_path_x" : onV ? "ground_path_v" : "ground_path_h";
          } else {
            ground = "ground_plaza";
          }
          if (ground) {
            if (trySprite(k, ground, pos, TILE_DRAW, TILE_DRAW)) drewAny = true;
            else {
              const paint = paintCell(cell);
              k.drawRect({
                pos: k.vec2(pos.x, pos.y),
                width: TILE_DRAW,
                height: TILE_DRAW,
                color: k.rgb(...paint.fill),
              });
            }
          }
          if (cell === "sundial") {
            k.drawCircle({
              pos: k.vec2(pos.x + TILE_DRAW / 2, pos.y + TILE_DRAW / 2),
              radius: 8,
              color: k.rgb(92, 83, 70),
              outline: { width: 2, color: k.rgb(176, 141, 79) },
            });
          }
          const dressed = map.layout.scenery.find((s) => s.tx === tx && s.ty === ty);
          if (dressed && cell === "grass") {
            trySprite(k, dressed.frame, pos, TILE_DRAW, TILE_DRAW);
          }
          const dist = map.layout.districts.find((d) => d.tx === tx && d.ty === ty);
          if (dist) {
            trySprite(k, dist.tool, { x: pos.x + 4, y: pos.y + 4 }, 24, 24);
            const tier = gs.town.outlineTier(dist.sleeveId);
            if (tier > 0) {
              k.drawRect({
                pos: k.vec2(pos.x, pos.y),
                width: TILE_DRAW,
                height: TILE_DRAW,
                fill: false,
                outline: {
                  width: tier === 2 ? 3 : 2,
                  color: k.rgb(176, 141, 79),
                },
              });
            }
          }
          if (
            flashDistrict &&
            flashDistrict.tx === tx &&
            flashDistrict.ty === ty
          ) {
            k.drawRect({
              pos: k.vec2(pos.x, pos.y),
              width: TILE_DRAW,
              height: TILE_DRAW,
              fill: false,
              outline: { width: 2, color: k.rgb(232, 228, 217) },
            });
          }
          if (hud.stretch > hud.criticalValue && cell === "stone") {
            for (let i = 0; i < 4; i++) {
              k.drawLine({
                p1: k.vec2(pos.x + i * 8, pos.y),
                p2: k.vec2(pos.x + i * 8 + 8, pos.y + TILE_DRAW),
                color: k.rgb(213, 94, 0),
                width: 1,
                opacity: 0.35,
              });
            }
          }
        }
      }
      atlasOk = drewAny && !missAny;

      // Dest brass plus (skip under reduced motion).
      if (dest && !gs.juice.reducedMotion) {
        const dpos = map.screenOf(dest.tx, dest.ty);
        const cx = dpos.x + TILE_DRAW / 2;
        const cy = dpos.y + TILE_DRAW / 2;
        const brass = k.rgb(176, 141, 79);
        k.drawLine({
          p1: k.vec2(cx - 8, cy),
          p2: k.vec2(cx + 8, cy),
          width: 2,
          color: brass,
        });
        k.drawLine({
          p1: k.vec2(cx, cy - 8),
          p2: k.vec2(cx, cy + 8),
          width: 2,
          color: brass,
        });
      }

      // Player: sprite optional; bone circle always visible as fallback.
      const base = map.screenOf(player.tx, player.ty);
      const hop = player.drawOffset(TILE_DRAW, gs.juice.reducedMotion);
      const ppos = { x: base.x + hop.x, y: base.y + hop.y };
      {
        const frame = player.spriteFrame();
        const drew =
          trySprite(k, frame, ppos, TILE_DRAW, TILE_DRAW) ||
          (frame.endsWith("_1") &&
            trySprite(k, frame.slice(0, -2), ppos, TILE_DRAW, TILE_DRAW));
        if (!drew) {
          const progress = (k as { loadProgress?: () => number }).loadProgress;
          const loaded = typeof progress === "function" ? progress.call(k) >= 1 : true;
          if (loaded && !artMissSent) {
            artMissSent = true;
            chat.markArtMissing();
          }
          k.drawCircle({
            pos: k.vec2(ppos.x + TILE_DRAW / 2, ppos.y + TILE_DRAW / 2),
            radius: 8,
            color: k.rgb(232, 228, 217),
          });
        }
      }

      // Mouseover: shadow under glyph, then yellow
      k.drawText({
        text: mouseover,
        pos: k.vec2(VIEWPORT_INNER.x + 7, VIEWPORT_INNER.y + 7),
        font: TYPE.mouse.font,
        size: TYPE.mouse.size,
        color: k.rgb(0, 0, 0),
        opacity: 0.55,
      });
      k.drawText({
        text: mouseover,
        pos: k.vec2(VIEWPORT_INNER.x + 6, VIEWPORT_INNER.y + 6),
        font: TYPE.mouse.font,
        size: TYPE.mouse.size,
        color: k.rgb(232, 228, 217),
      });

      if (showHowToWalk) {
        const card = howToCard();
        k.drawRect({
          pos: k.vec2(card.x, card.y),
          width: card.w,
          height: card.h,
          color: k.rgb(216, 201, 168),
          outline: { width: 3, color: k.rgb(176, 141, 79) },
        });
        k.drawText({
          text: "How to play",
          pos: k.vec2(card.x + 16, card.y + 12),
          font: TYPE.title.font,
          size: TYPE.title.size,
          color: k.rgb(42, 36, 28),
        });
        for (const row of card.rows) {
          k.drawText({
            text: row.rule,
            pos: k.vec2(card.x + 16, card.y + row.y),
            font: TYPE.chat.font,
            size: TYPE.chat.size,
            color: k.rgb(42, 36, 28),
            width: card.w - 32,
          });
        }
      }

      drawMinimap(k, map, player, hud.heat, atlasOk);

      // Pack panel (outlined well; no stretched 32px sprite)
      drawWell(
        (o) => {
          k.drawRect({
            pos: k.vec2(o.x, o.y),
            width: o.w,
            height: o.h,
            color: k.rgb(...o.fill),
            outline: { width: o.outlineWidth, color: k.rgb(...o.outline) },
          });
        },
        PACK.x,
        PACK.y,
        PACK.w,
        PACK.h,
        WELL_STONE,
        WELL_BRASS
      );
      for (const corner of ["ui_corner_tl", "ui_corner_tr", "ui_corner_bl", "ui_corner_br"] as const) {
        const cx =
          corner.endsWith("tr") || corner.endsWith("br")
            ? PACK.x + PACK.w - 16
            : PACK.x;
        const cy =
          corner.endsWith("bl") || corner.endsWith("br")
            ? PACK.y + PACK.h - 16
            : PACK.y;
        trySprite(k, corner, { x: cx, y: cy }, 16, 16);
      }
      k.drawText({
        text: "Your books",
        pos: k.vec2(PACK.x + 12, PACK.y + 10),
        font: TYPE.chat.font,
        size: TYPE.chat.size,
        color: k.rgb(216, 201, 168),
      });
      for (let i = 0; i < sleeves.length; i++) {
        const r = slotRect(i);
        if (!trySprite(k, "inv_slot", r, r.w, r.h)) {
          k.drawRect({
            pos: k.vec2(r.x, r.y),
            width: r.w,
            height: r.h,
            fill: false,
            outline: { width: 1, color: k.rgb(176, 141, 79) },
          });
        }
        const s = sleeves[i]!;
        const selected = gs.portfolio.selectedIndex === i;
        const d = DISTRICTS.find((x) => x.sleeveId === s.def.id);
        if (d) trySprite(k, d.tool, { x: r.x + 2, y: r.y + 2 }, 18, 18);
        k.drawText({
          text: `${qty[s.def.id] ?? 0}`,
          pos: k.vec2(r.x + r.w - 2, r.y + r.h - 16),
          anchor: "topright",
          font: TYPE.hud.font,
          size: TYPE.hud.size,
          color: k.rgb(232, 228, 217),
        });
        if (selected) {
          k.drawRect({
            pos: k.vec2(r.x, r.y),
            width: r.w,
            height: r.h,
            fill: false,
            outline: { width: 2, color: k.rgb(232, 228, 217) },
          });
        }
      }
      // Worn Book above the empty pack well
      k.drawText({
        text: "Worn: Stillbook",
        pos: k.vec2(PACK.x + 12, PACK.y + 300),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(216, 201, 168),
      });

      // Chat well (no stretched chat_panel)
      drawWell(
        (o) => {
          k.drawRect({
            pos: k.vec2(o.x, o.y),
            width: o.w,
            height: o.h,
            color: k.rgb(...o.fill),
            outline: { width: o.outlineWidth, color: k.rgb(...o.outline) },
          });
        },
        CHAT.x,
        CHAT.y,
        CHAT.w,
        CHAT.h,
        WELL_PARCHMENT,
        WELL_BRASS
      );
      const lines = chat.visible();
      const chatWidth = CHAT.w - 24;
      let lineY = CHAT.y + CHAT.h - 52;
      for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i]!;
        const block = textBlockHeight(k, line.text, TYPE.chat.font, TYPE.chat.size, chatWidth);
        lineY -= block;
        if (lineY < CHAT.y + 8) break;
        const col =
          line.tone === "alert" ? k.rgb(96, 16, 16) : k.rgb(42, 36, 28);
        k.drawText({
          text: line.text,
          pos: k.vec2(CHAT.x + 10, lineY),
          font: TYPE.chat.font,
          size: TYPE.chat.size,
          color: col,
          width: chatWidth,
        });
      }
      const tapeLine = ticker.line(gs.tape.currentAsOf(), hud, gs.tape.dataSource);
      k.drawText({
        text: tapeLine.slice(0, 90),
        pos: k.vec2(CHAT.x + 10, CHAT.y + CHAT.h - 36),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(42, 36, 28),
        width: CHAT.w - 24,
      });
      k.drawText({
        text: ">",
        pos: k.vec2(CHAT.x + 10, CHAT.y + CHAT.h - 18),
        font: TYPE.chat.font,
        size: TYPE.chat.size,
        color: k.rgb(42, 36, 28),
      });

      // Orb cluster + STAMP
      k.drawRect({
        pos: k.vec2(ORB_CLUSTER.x, ORB_CLUSTER.y),
        width: ORB_CLUSTER.w,
        height: ORB_CLUSTER.h,
        color: k.rgb(58, 52, 44),
        outline: { width: 2, color: k.rgb(176, 141, 79) },
      });
      const stretchLit = hud.bubbleFlag || hud.stretch > hud.criticalValue;
      k.drawRect({
        pos: k.vec2(ORB_CLUSTER.x + 24, ORB_CLUSTER.y + 16),
        width: 28,
        height: 28,
        color: stretchLit ? k.rgb(213, 94, 0) : k.rgb(92, 83, 70),
        fill: stretchLit,
        outline: { width: 2, color: k.rgb(176, 141, 79) },
      });
      k.drawText({
        text: stretchLit ? "marked" : "clear",
        pos: k.vec2(ORB_CLUSTER.x + 60, ORB_CLUSTER.y + 22),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(216, 201, 168),
      });
      k.drawText({
        text: `turn ${gs.sessionTurns + 1}/${gs.maxTurnsPerSession}`,
        pos: k.vec2(ORB_CLUSTER.x + 24, ORB_CLUSTER.y + 56),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(216, 201, 168),
      });
      k.drawText({
        text: `score ${gs.score.totalScore.toFixed(3)}`,
        pos: k.vec2(ORB_CLUSTER.x + 24, ORB_CLUSTER.y + 76),
        font: TYPE.hud.font,
        size: TYPE.hud.size,
        color: k.rgb(216, 201, 168),
      });

      drawWell(
        (o) => {
          k.drawRect({
            pos: k.vec2(o.x, o.y),
            width: o.w * stampScale,
            height: o.h * stampScale,
            color: k.rgb(...o.fill),
            outline: { width: o.outlineWidth, color: k.rgb(...o.outline) },
          });
        },
        STAMP.x + (STAMP.w * (1 - stampScale)) / 2,
        STAMP.y + (STAMP.h * (1 - stampScale)) / 2,
        STAMP.w,
        STAMP.h,
        WELL_STONE,
        WELL_BRASS
      );
      // Native-size stone glyph only (never stretch past 32px).
      trySprite(
        k,
        "btn_stone",
        {
          x: STAMP.x + STAMP.w / 2 - 16,
          y: STAMP.y + STAMP.h / 2 - 16,
        },
        32,
        32
      );
      k.drawText({
        text: "STAMP",
        pos: k.vec2(STAMP.x + STAMP.w / 2, STAMP.y + STAMP.h / 2),
        anchor: "center",
        font: TYPE.stamp.font,
        size: TYPE.stamp.size,
        color: k.rgb(232, 228, 217),
      });

      if (printPopup) {
        const sun = map.screenOf(map.layout.sundial.tx, map.layout.sundial.ty);
        trySprite(
          k,
          printPopup.up ? "fx_star" : "fx_spark",
          { x: sun.x + 8, y: sun.y - 8 - printPopup.y },
          16,
          16
        );
        k.drawRect({
          pos: k.vec2(sun.x - 28, sun.y - printPopup.y - 12),
          width: 88,
          height: 22,
          color: k.rgb(42, 36, 28),
        });
        k.drawText({
          text: printPopup.text,
          pos: k.vec2(sun.x + 16, sun.y - printPopup.y),
          anchor: "center",
          font: TYPE.hud.font,
          size: TYPE.hud.size,
          color: k.rgb(232, 228, 217),
        });
      }

      if (menu) {
        const openMenu = menu;
        const mh = 28 + openMenu.options.length * 22;
        k.drawRect({
          pos: k.vec2(openMenu.x, openMenu.y),
          width: 200,
          height: mh,
          color: k.rgb(0, 0, 0),
          opacity: 0.9,
        });
        k.drawText({
          text: openMenu.title,
          pos: k.vec2(openMenu.x + 8, openMenu.y + 6),
          font: TYPE.mouse.font,
          size: TYPE.mouse.size,
          color: k.rgb(232, 228, 217),
        });
        openMenu.options.forEach((opt, i) => {
          k.drawText({
            text: opt.label,
            pos: k.vec2(openMenu.x + 8, openMenu.y + 28 + i * 22),
            font: TYPE.chat.font,
            size: TYPE.chat.size,
            color: k.rgb(232, 228, 217),
          });
        });
      }

      if (gs.paused) {
        k.drawRect({
          pos: k.vec2(0, 0),
          width: W,
          height: H,
          color: k.rgb(0, 0, 0),
          opacity: 0.55,
        });
        k.drawText({
          text: "Click to wake the desk",
          pos: k.vec2(W / 2, H / 2),
          anchor: "center",
          font: TYPE.title.font,
          size: TYPE.title.size,
          color: k.rgb(232, 228, 217),
        });
      }
    });

    k.onKeyPress("+", () => {
      if (gs.paused || phase === "locked" || phase === "resolving") return;
      gs.portfolio.bumpSelected(0.05);
      phase = "targeting";
    });
    k.onKeyPress("-", () => {
      if (gs.paused || phase === "locked" || phase === "resolving") return;
      gs.portfolio.bumpSelected(-0.05);
      phase = "targeting";
    });
    k.onKeyPress("space", () => commitSync());
    const queueStep = (dx: number, dy: number) => {
      showHowToWalk = false;
      pendingStep = { dx, dy };
    };
    k.onKeyPress("left", () => queueStep(-1, 0));
    k.onKeyPress("a", () => queueStep(-1, 0));
    k.onKeyPress("right", () => queueStep(1, 0));
    k.onKeyPress("d", () => queueStep(1, 0));
    k.onKeyPress("up", () => queueStep(0, -1));
    k.onKeyPress("w", () => queueStep(0, -1));
    k.onKeyPress("down", () => queueStep(0, 1));
    k.onKeyPress("s", () => queueStep(0, 1));

    k.onKeyPress("escape", () => {
      if (menu) {
        menu = null;
        return;
      }
      gs.paused = !gs.paused;
      if (gs.paused) gs.bridge.post({ type: "requestFocus" });
    });
    k.onKeyPress("m", () => {
      gs.audio.setMuted(!gs.audio.muted);
    });
    k.onKeyPress("e", () => {
      examineAtTile(player.tx, player.ty);
    });

    try {
      k.canvas?.addEventListener("contextmenu", (ev) => ev.preventDefault());
    } catch {
      /* ignore */
    }

    k.onMouseMove(() => {
      const mp = k.mousePos();
      const tile = map.tileAtScreen(mp.x, mp.y);
      if (tile) {
        const dist = map.layout.districts.find(
          (d) => d.tx === tile.tx && d.ty === tile.ty
        );
        if (dist) mouseover = `${dist.verb} ${dist.place}`;
        else if (
          tile.tx === map.layout.sundial.tx &&
          tile.ty === map.layout.sundial.ty
        )
          mouseover = "Stamp sundial";
        else if (map.layout.stones.some((s) => s.tx === tile.tx && s.ty === tile.ty))
          mouseover = "Examine stone";
        else mouseover = "Walk here";
        return;
      }
      for (let i = 0; i < sleeves.length; i++) {
        const r = slotRect(i);
        if (hitTest(mp.x, mp.y, r)) {
          mouseover = `Select ${sleeves[i]!.def.label}`;
          return;
        }
      }
      if (
        mp.x >= PACK.x &&
        mp.x < PACK.x + PACK.w &&
        mp.y >= PACK.y + 296 &&
        mp.y < PACK.y + PACK.h
      ) {
        mouseover = "Examine Stillbook";
        return;
      }
      if (hitTest(mp.x, mp.y, STAMP)) mouseover = "Stamp Book";
      else mouseover = "";
    });

    k.onClick(() => {
      if (gs.paused || phase === "locked" || phase === "resolving") return;
      const mp = k.mousePos();
      if (showHowToWalk) {
        const card = howToCard();
        if (hitTest(mp.x, mp.y, card)) return;
      }
      if (menu) {
        const open = menu;
        const panel = { x: open.x, y: open.y, w: 200, h: 28 + open.options.length * 22 };
        if (!hitTest(mp.x, mp.y, panel)) {
          menu = null;
          return;
        }
        const optIdx = Math.floor((mp.y - open.y - 28) / 22);
        if (optIdx >= 0 && optIdx < open.options.length) {
          open.options[optIdx]!.action();
        }
        menu = null;
        return;
      }
      if (hitTest(mp.x, mp.y, STAMP)) {
        commitSync();
        return;
      }
      const miniTile = minimapTileAt(mp.x, mp.y);
      if (miniTile) {
        queueWalk(miniTile.tx, miniTile.ty);
        return;
      }
      for (let i = 0; i < sleeves.length; i++) {
        const r = slotRect(i);
        if (!hitTest(mp.x, mp.y, r)) continue;
        gs.portfolio.selectIndex(i);
        phase = "targeting";
        gs.juice.uiClick();
        return;
      }
      if (
        mp.x >= PACK.x &&
        mp.x < PACK.x + PACK.w &&
        mp.y >= PACK.y + 296 &&
        mp.y < PACK.y + PACK.h
      ) {
        const hud = gs.tape.benchmarkHud();
        const sel = sleeveIds[gs.portfolio.selectedIndex] ?? sleeveIds[0]!;
        chat.push(
          examineBook(
            gs.tape.currentAsOf(),
            hud.heat,
            hud.stretch,
            hud.criticalValue,
            gs.album.count(),
            {
              sleeveId: sel,
              visitCount: gs.town.visitCount(sel),
            }
          ),
          "examine"
        );
        return;
      }
      if (hitTest(mp.x, mp.y, CHAT)) return;
      const tile = map.tileAtScreen(mp.x, mp.y);
      if (tile) queueWalk(tile.tx, tile.ty);
    });

    k.onMousePress("right", () => {
      if (gs.paused || phase === "locked" || phase === "resolving") return;
      const mp = k.mousePos();
      for (let i = 0; i < sleeves.length; i++) {
        const r = slotRect(i);
        if (!hitTest(mp.x, mp.y, r)) continue;
        const sleeve = sleeves[i]!;
        menu = {
          x: Math.min(mp.x, CANVAS.w - 210),
          y: Math.min(mp.y, CANVAS.h - 120),
          title: sleeve.def.label,
          options: [
            {
              label: "Add weight",
              action: () => bumpSleeve(i, 0.05),
            },
            {
              label: "Shed weight",
              action: () => bumpSleeve(i, -0.05),
            },
            {
              label: "Examine",
              action: () => {
                gs.portfolio.selectIndex(i);
                chat.push(examineEmptySlot(), "examine");
              },
            },
            { label: "Cancel", action: () => undefined },
          ],
        };
        return;
      }
      const tile = map.tileAtScreen(mp.x, mp.y);
      if (!tile) return;
      const dist = map.layout.districts.find(
        (d) => d.tx === tile.tx && d.ty === tile.ty
      );
      const stone = map.layout.stones.find(
        (s) => s.tx === tile.tx && s.ty === tile.ty
      );
      const isSundial =
        tile.tx === map.layout.sundial.tx && tile.ty === map.layout.sundial.ty;
      const defaultLabel = dist
        ? `${dist.verb} ${dist.place}`
        : isSundial
          ? "Stamp sundial"
          : stone
            ? `Touch ${stone.title}`
            : "Walk here";
      menu = {
        x: Math.min(mp.x, CANVAS.w - 210),
        y: Math.min(mp.y, CANVAS.h - 120),
        title: "Choose",
        options: [
          {
            label: defaultLabel,
            action: () => {
              queueWalk(tile.tx, tile.ty);
            },
          },
          {
            label: "Examine",
            action: () => examineAtTile(tile.tx, tile.ty),
          },
          {
            label: "Rules",
            action: () => pushRules(),
          },
          { label: "Cancel", action: () => undefined },
        ],
      };
    });
  });
}
