import { glossary, regimeKey } from "../../copy/glossary";
import { Hint } from "../ui/Hint";

type Regime = "normal" | "boom" | "bust";

const REGIME_SHAPE: Record<Regime, "circle" | "triangle" | "square"> = {
  normal: "circle",
  boom: "triangle",
  bust: "square",
};

const REGIME_COLOR: Record<Regime, string> = {
  normal: "var(--color-normal)",
  boom: "var(--color-elevated)",
  bust: "var(--color-high)",
};

export function RegimeBadge({ regime }: { regime: Regime }) {
  const key = regimeKey(regime);
  const label = glossary[key].label;

  return (
    <Hint entry={key}>
      <div className="regime-badge" style={{ background: REGIME_COLOR[regime] }}>
        <span className="regime-shape" data-shape={REGIME_SHAPE[regime]} />
        <span className="regime-label">{label}</span>
      </div>
    </Hint>
  );
}
