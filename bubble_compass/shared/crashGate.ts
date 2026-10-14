/** Tape-derived crash trigger (regime_state alone is insufficient on published tape). */

export type CrashGateInput = {
  heat: number;
  bubbleFlag: boolean;
  stretch: number;
  criticalValue: number;
  portfolioReturn: number;
};

export type CrashGateResult = {
  triggered: boolean;
  reason: string;
};

export function evaluateCrashGate(input: CrashGateInput): CrashGateResult {
  const { heat, bubbleFlag, stretch, criticalValue, portfolioReturn } = input;
  if (heat >= 70) {
    return { triggered: true, reason: `heat=${heat.toFixed(0)}>=70` };
  }
  if (bubbleFlag && portfolioReturn < -0.02) {
    return {
      triggered: true,
      reason: `bubble_flag && portfolioReturn=${(portfolioReturn * 100).toFixed(2)}%`,
    };
  }
  if (stretch > criticalValue + 0.5 && portfolioReturn < -0.02) {
    return {
      triggered: true,
      reason: `stretch=${stretch.toFixed(2)}>cv+0.5 && loss`,
    };
  }
  return { triggered: false, reason: "" };
}
