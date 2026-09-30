import { useMarketStore } from "../../store/marketStore";
import { glossary } from "../../copy/glossary";
import { HintLabel } from "../ui/Hint";
import { Hint } from "../ui/Hint";

export function QuickFacts() {
  const asset = useMarketStore((s) => s.currentAsset);
  const state = useMarketStore((s) => s.getAssetState(asset));

  const stretchValue = state.bsadf.bubbleFlag
    ? `${state.bsadf.bsadfStat.toFixed(2)} above ${state.bsadf.criticalValue.toFixed(2)} · live`
    : `${state.bsadf.bsadfStat.toFixed(2)} under ${state.bsadf.criticalValue.toFixed(2)} · quiet`;

  const crashValue =
    state.lppls.crashWindowStart && state.lppls.crashWindowEnd
      ? `${(state.lppls.lppConfidence * 100).toFixed(0)}% · ${state.lppls.crashWindowStart
          .toISOString()
          .slice(0, 10)} → ${state.lppls.crashWindowEnd.toISOString().slice(0, 10)}`
      : `${(state.lppls.lppConfidence * 100).toFixed(0)}% · no window yet`;

  const toneValue = state.sentiment.unavailable
    ? "unavailable"
    : (() => {
        const toneSign =
          state.sentiment.sentimentLevel >= 0
            ? `+${state.sentiment.sentimentLevel.toFixed(2)}`
            : state.sentiment.sentimentLevel.toFixed(2);
        const rateSign =
          state.sentiment.sentimentVelocity >= 0
            ? `rising ${state.sentiment.sentimentVelocity.toFixed(2)}`
            : `falling ${Math.abs(state.sentiment.sentimentVelocity).toFixed(2)}`;
        return `${toneSign} · ${rateSign}`;
      })();

  return (
    <div className="quick-facts">
      <p className="panel-title">
        <HintLabel entry="evidence" />
      </p>
      <Hint entry="stretchTest">
        <div className="quick-fact">
          <span className="quick-fact-label">{glossary.stretchTest.label}</span>
          <span className="quick-fact-value">{stretchValue}</span>
        </div>
      </Hint>
      <Hint entry="crashTiming">
        <div className="quick-fact">
          <span className="quick-fact-label">{glossary.crashTiming.label}</span>
          <span className="quick-fact-value">{crashValue}</span>
        </div>
      </Hint>
      <Hint entry="newsTone">
        <div className="quick-fact">
          <span className="quick-fact-label">{glossary.newsTone.label}</span>
          <span className="quick-fact-value">{toneValue}</span>
        </div>
      </Hint>
    </div>
  );
}
