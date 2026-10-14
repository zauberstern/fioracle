import { Group, Panel, Separator } from "react-resizable-panels";
import { useMarketStore } from "../../store/marketStore";
import { glossary, regimeKey } from "../../copy/glossary";
import { statusWord } from "../../narrator/heat";
import { StatusMark } from "../reading/StatusMark";
import { BubbleGauge } from "./BubbleGauge";
import { RegimeBadge } from "./RegimeBadge";
import { QuickFacts } from "./QuickFacts";
import { EvidencePanel } from "./EvidencePanel";
import { StoryPanel } from "./StoryPanel";
import { CompanyDebtGrid, type DebtGridRow } from "./CompanyDebtGrid";
import { HintLabel } from "../ui/Hint";
import { ToneVsMarketGauge } from "../credit/ToneVsMarketGauge";
import { PDDisagreementCloud } from "../credit/PDDisagreementCloud";
import { CreditSurfaceTracker } from "../credit/CreditSurfaceTracker";
import { CliffMap } from "../credit/CliffMap";
import { BreachCalendar } from "../credit/BreachCalendar";
import { StressLanguageScore } from "../credit/StressLanguageScore";
import "../credit/credit.css";
import "./company-debt.css";

const ISSUER_GATE =
  "Issuer CDS / Compustat / transcripts not entitled offline";

function tipRow(
  layers: Record<string, Array<Record<string, unknown>>>,
  layer: string
): Record<string, unknown> | null {
  const rows = layers[layer];
  if (!rows?.length) return null;
  return rows[rows.length - 1] ?? null;
}

export function LeftRail() {
  const asset = useMarketStore((s) => s.currentAsset);
  const bubbleScore = useMarketStore((s) => s.bubbleScore);
  const regime = useMarketStore((s) => s.getAssetState(asset).regime.regimeState);
  const layers = useMarketStore((s) => s.rawLayers);
  const debt = tipRow(layers, "macro_debt");
  const credit = tipRow(layers, "credit_trajectory");
  const debtRows: DebtGridRow[] = [
    {
      id: "US_DEBT_TO_GDP",
      label: "US Debt/GDP %",
      seriesType: "OTHER",
      value: debt?.debt_to_gdp != null ? Number(debt.debt_to_gdp) : null,
      asOf: debt?.as_of != null ? String(debt.as_of).slice(0, 10) : "history",
    },
    {
      id: "HY_OAS",
      label: "HY OAS (bps)",
      seriesType: "OAS",
      value:
        credit?.hy_oas_level_bps != null ? Number(credit.hy_oas_level_bps) : null,
      asOf: credit?.as_of != null ? String(credit.as_of).slice(0, 10) : "history",
    },
    {
      id: "VIX",
      label: "VIX",
      seriesType: "OTHER",
      value: credit?.vix != null ? Number(credit.vix) : null,
      asOf: credit?.as_of != null ? String(credit.as_of).slice(0, 10) : "history",
    },
  ];

  return (
    <aside className="left-rail">
      <p className="panel-title">
        <HintLabel entry="bubbleScore" />
      </p>
      <BubbleGauge score={bubbleScore} />
      <div style={{ display: "flex", justifyContent: "center" }}>
        <RegimeBadge regime={regime} />
      </div>
      <QuickFacts />
      <StoryPanel />
      <CompanyDebtGrid rows={debtRows} />
    </aside>
  );
}

export function Dashboard() {
  const asset = useMarketStore((s) => s.currentAsset);
  const bubbleScore = useMarketStore((s) => s.bubbleScore);
  const regime = useMarketStore((s) => s.getAssetState(asset).regime);
  const layers = useMarketStore((s) => s.rawLayers);
  const historySource = useMarketStore((s) => s.historySource);
  const stateLabel = glossary[regimeKey(regime.regimeState)].label;
  const credit = tipRow(layers, "credit_trajectory");
  const toneUnavailable = credit == null || Boolean(credit.tone_unavailable ?? true);
  const toneValue =
    credit?.tone_value != null && Number.isFinite(Number(credit.tone_value))
      ? Number(credit.tone_value)
      : null;

  return (
    <div className="dashboard-root">
      <Group orientation="vertical" style={{ height: "100%" }}>
        <Panel id="hero" defaultSize="36" minSize="24">
          <div className="dashboard-main">
            <div className="dashboard-hero">
              <div className="dashboard-hero-copy">
                <h2 className="weekly-status-row">
                  <StatusMark word={statusWord(bubbleScore)} />
                  <span>
                    {glossary.bubbleScore.label} {bubbleScore.toFixed(1)}
                  </span>
                </h2>
                <p>
                  {statusWord(bubbleScore)} on this book. Warming starts at 40.
                  Stretched starts at 70. The market state is {stateLabel}, with{" "}
                  {(regime.regimeConfidence * 100).toFixed(0)} percent confidence.
                  {historySource === "empty"
                    ? " No history is loaded."
                    : " The chart below is this book's history."}
                </p>
              </div>
              <BubbleGauge score={bubbleScore} />
            </div>
            <div className="credit-radar-grid">
              <ToneVsMarketGauge
                value={toneValue}
                unavailable={toneUnavailable}
                reason={
                  toneUnavailable
                    ? "Need VIX and the high-yield spread change in this history (or management tone)"
                    : undefined
                }
                source="vix_oas_proxy"
              />
              <PDDisagreementCloud unavailable reason={ISSUER_GATE} />
              <CreditSurfaceTracker
                unavailable
                reason="Index surface only; issuer LTV panels not offline"
              />
              <CliffMap unavailable reason={ISSUER_GATE} />
              <BreachCalendar unavailable reason={ISSUER_GATE} />
              <StressLanguageScore unavailable reason="No 10-K text corpus in catalog" />
            </div>
          </div>
        </Panel>
        <Separator className="resize-handle-row" />
        <Panel id="evidence" defaultSize="64" minSize="30">
          <EvidencePanel />
        </Panel>
      </Group>
    </div>
  );
}
