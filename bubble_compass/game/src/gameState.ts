import { Portfolio } from "./entities/Portfolio";
import { ScoreKeeper } from "./systems/ScoreKeeper";
import { TapePlayer } from "./systems/TapePlayer";

export const gameState = {
  tape: new TapePlayer(),
  portfolio: new Portfolio(),
  score: new ScoreKeeper(),
  sessionTurns: 0,
  maxTurnsPerSession: 5,
  lastTurnScore: 0,
  crashTriggered: false,
};
