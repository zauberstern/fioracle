import { heatBandLabel, glossary } from "../../copy/glossary";
import { Hint } from "../ui/Hint";

interface BubbleGaugeProps {
  score: number;
}

function getColor(s: number): string {
  if (s < 40) return "var(--color-normal)";
  if (s < 70) return "var(--color-elevated)";
  return "var(--color-high)";
}

export function BubbleGauge({ score }: BubbleGaugeProps) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const radius = 90;
  const circumference = Math.PI * radius;
  const progress = (clampedScore / 100) * circumference;
  const color = getColor(clampedScore);
  const band = heatBandLabel(clampedScore);
  const label = glossary[band].label;

  return (
    <Hint entry="bubbleScore" extra={glossary[band].tech}>
      <div
        className="gauge-container"
        role="meter"
        aria-valuenow={clampedScore}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${clampedScore.toFixed(1)}, ${label}`}
      >
        <svg viewBox="0 0 200 120" width="200" height="120" aria-hidden="true">
          <path
            d="M 10 110 A 90 90 0 0 1 190 110"
            fill="none"
            stroke="var(--border-hairline)"
            strokeWidth="12"
            strokeLinecap="round"
          />
          <path
            d="M 10 110 A 90 90 0 0 1 190 110"
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
          />
        </svg>
        <div className="gauge-value">
          <span className="gauge-number" style={{ color }}>
            {clampedScore.toFixed(1)}
          </span>
          <span className="gauge-label">{label}</span>
        </div>
      </div>
    </Hint>
  );
}
