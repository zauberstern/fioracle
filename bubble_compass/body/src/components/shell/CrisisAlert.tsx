import { useMarketStore } from "../../store/marketStore";
import { crisisHeadline } from "../../copy/sensational";
import { Hint } from "../ui/Hint";

export function CrisisAlert() {
  const asset = useMarketStore((s) => s.currentAsset);
  const score = useMarketStore((s) => s.bubbleScore);
  if (score <= 70) return null;

  return (
    <Hint entry="crisisAlert">
      <div className="crisis-alert" role="alert">
        <span className="crisis-alert-tag">CRISIS</span>
        <span className="crisis-alert-copy">{crisisHeadline(asset, score)}</span>
      </div>
    </Hint>
  );
}
