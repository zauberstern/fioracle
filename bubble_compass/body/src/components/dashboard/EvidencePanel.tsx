import * as Tabs from "@radix-ui/react-tabs";
import { glossary } from "../../copy/glossary";
import { Hint } from "../ui/Hint";
import { ScoreChart } from "./ScoreChart";
import { BSADFChart } from "./BSADFChart";
import { LPPLSChart } from "./LPPLSChart";
import { SentimentChart } from "./SentimentChart";
import { ReplayControls } from "./ReplayControls";

function TabLabel({
  entry,
  value,
}: {
  entry: "heatHistory" | "stretchTest" | "crashTiming" | "newsTone" | "scrubHistory";
  value: string;
}) {
  return (
    <Tabs.Trigger value={value}>
      <Hint entry={entry}>{glossary[entry].label}</Hint>
    </Tabs.Trigger>
  );
}

export function EvidencePanel() {
  return (
    <Tabs.Root className="evidence-panel" defaultValue="score">
      <Tabs.List className="evidence-tabs" aria-label="Detail charts">
        <TabLabel entry="heatHistory" value="score" />
        <TabLabel entry="stretchTest" value="bsadf" />
        <TabLabel entry="crashTiming" value="lppls" />
        <TabLabel entry="newsTone" value="sentiment" />
        <TabLabel entry="scrubHistory" value="replay" />
      </Tabs.List>
      <div className="evidence-body">
        <Tabs.Content value="score">
          <ScoreChart />
        </Tabs.Content>
        <Tabs.Content value="bsadf">
          <BSADFChart />
        </Tabs.Content>
        <Tabs.Content value="lppls">
          <LPPLSChart />
        </Tabs.Content>
        <Tabs.Content value="sentiment">
          <SentimentChart />
        </Tabs.Content>
        <Tabs.Content value="replay">
          <ReplayControls />
        </Tabs.Content>
      </div>
    </Tabs.Root>
  );
}
