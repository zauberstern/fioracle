import { Group, Panel, Separator } from "react-resizable-panels";
import { useMarketStore } from "../../store/marketStore";
import { glossary, regimeKey } from "../../copy/glossary";
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

const INDEX_DEBT_ROWS: DebtGridRow[] = [
  {
    id: "BBG_US_HIGH_YIELD_TOTAL_RETURN",
    label: "US High Yield TR",
    seriesType: "OTHER",
    value: null,
    asOf: "catalog",
  },
  {
    id: "CDX_HY_5Y_TOTAL_RETURN",
    label: "CDX HY 5Y TR",
    seriesType: "CDX",
    value: null,
    asOf: "catalog",
  },
  {
    id: "CDX_IG_5Y_TOTAL_RETURN",
    label: "CDX IG 5Y TR",
    seriesType: "CDX",
    value: null,
    asOf: "catalog",
  },
  {
    id: "US_HY_CORP_OAS_TOTAL_RETURN",
    label: "HY Corp OAS",
    seriesType: "OAS",
    value: null,
    asOf: "catalog",
  },
  {
    id: "US_DEBT_TO_GDP",
    label: "US Debt/GDP",
    seriesType: "OTHER",
    value: null,
    asOf: "catalog",
  },
];

const CREDIT_GATE =
  "Issuer CDS / Compustat / transcripts not entitled; index CDX + HY OAS wired in catalog";

export function LeftRail() {
  const asset = useMarketStore((s) => s.currentAsset);
  const bubbleScore = useMarketStore((s) => s.bubbleScore);
  const regime = useMarketStore((s) => s.getAssetState(asset).regime.regimeState);

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
      <CompanyDebtGrid rows={INDEX_DEBT_ROWS} />
    </aside>
  );
}

export function Dashboard() {
  const asset = useMarketStore((s) => s.currentAsset);
  const bubbleScore = useMarketStore((s) => s.bubbleScore);
  const regime = useMarketStore((s) => s.getAssetState(asset).regime);
  const stateLabel = glossary[regimeKey(regime.regimeState)].label;

  return (
    <div className="dashboard-root">
      <Group orientation="vertical" style={{ height: "100%" }}>
        <Panel id="hero" defaultSize="36" minSize="24">
          <div className="dashboard-main">
            <div className="dashboard-hero">
              <div className="dashboard-hero-copy">
                <h2>
                  {asset}: {glossary.bubbleScore.label} {bubbleScore.toFixed(1)}
                </h2>
                <p>
                  Market state is {stateLabel} (
                  {(regime.regimeConfidence * 100).toFixed(0)}% sure). Timeline spine
                  below is the real history tape - not seeded sine waves.
                </p>
              </div>
              <BubbleGauge score={bubbleScore} />
            </div>
            <div className="credit-radar-grid">
              <ToneVsMarketGauge
                value={null}
                unavailable
                reason={CREDIT_GATE}
                source="vix_oas_proxy_or_transcripts"
              />
              <PDDisagreementCloud unavailable reason={CREDIT_GATE} />
              <CreditSurfaceTracker unavailable reason={CREDIT_GATE} />
              <CliffMap unavailable reason={CREDIT_GATE} />
              <BreachCalendar unavailable reason={CREDIT_GATE} />
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
