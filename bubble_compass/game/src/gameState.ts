import { Portfolio } from "./entities/Portfolio";
import { AudioBus } from "./systems/AudioBus";
import { Bridge } from "./systems/Bridge";
import { JuiceBus } from "./systems/JuiceBus";
import { ScoreKeeper } from "./systems/ScoreKeeper";
import { StampAlbum } from "./systems/StampAlbum";
import { TapePlayer } from "./systems/TapePlayer";
import { TownMemory } from "./systems/TownMemory";
import type { TurnScoreBreakdown } from "./systems/ScoreKeeper";

export type Session = {
  v: 1;
  turn: number;
  maxTurns: number;
  asOf: string;
  weights: Record<string, number>;
  scoreCumulative: number;
  lastBreakdown: TurnScoreBreakdown | null;
  crashTriggered: boolean;
  crashReason: string;
  paused: boolean;
  focused: boolean;
  bus: { sfx: number; music: number; muted: boolean };
  reducedMotion: boolean;
  tapeSource: "api" | "static" | "empty";
};

export const gameState = {
  tape: new TapePlayer(),
  portfolio: new Portfolio(),
  score: new ScoreKeeper(),
  album: new StampAlbum(),
  town: new TownMemory(),
  audio: new AudioBus(),
  juice: new JuiceBus(),
  bridge: new Bridge(),
  sessionTurns: 0,
  maxTurnsPerSession: 12,
  lastTurnScore: 0,
  crashTriggered: false,
  crashReason: "",
  paused: false,
  focused: false,
  lastBreakdown: null as TurnScoreBreakdown | null,
  /** Parent weekly as-of; title keeps this unless the player picks a stone. */
  parentAsOf: "" as string,
  episodePickedByUser: false,
  /** Desk ignores inbound asOf while a stamp is resolving. */
  ignoreInboundAsOf: false,
};

export function snapshotSession(): Session {
  return {
    v: 1,
    turn: gameState.sessionTurns,
    maxTurns: gameState.maxTurnsPerSession,
    asOf: gameState.tape.currentAsOf(),
    weights: gameState.portfolio.weights,
    scoreCumulative: gameState.score.totalScore,
    lastBreakdown: gameState.lastBreakdown,
    crashTriggered: gameState.crashTriggered,
    crashReason: gameState.crashReason,
    paused: gameState.paused,
    focused: gameState.focused,
    bus: {
      sfx: gameState.audio.sfx,
      music: gameState.audio.music,
      muted: gameState.audio.muted,
    },
    reducedMotion: gameState.juice.reducedMotion,
    tapeSource: gameState.tape.dataSource,
  };
}

export function persistSession(): void {
  gameState.portfolio.persist({
    turn: gameState.sessionTurns,
    asOf: gameState.tape.currentAsOf(),
    scoreCumulative: gameState.score.totalScore,
    crashTriggered: gameState.crashTriggered,
    crashReason: gameState.crashReason,
    bus: {
      sfx: gameState.audio.sfx,
      music: gameState.audio.music,
      muted: gameState.audio.muted,
    },
    reducedMotion: gameState.juice.reducedMotion,
    tapeSource: gameState.tape.dataSource,
  });
}

export type GameState = typeof gameState;
