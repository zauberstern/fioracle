import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";
import { ScoreChart } from "./ScoreChart";
import { BSADFChart } from "./BSADFChart";
import { LPPLSChart } from "./LPPLSChart";
import { SentimentChart } from "./SentimentChart";

const TABS = [
  {
    value: "score",
    label: "Heat",
    note: "Heat for this book. Quiet is under 40. Warming starts at 40. Stretched starts at 70.",
  },
  {
    value: "bsadf",
    label: "Fast rise",
    note: "How fast the rise is, against the ordinary line. A reading far above that line is drawn at the top of the chart.",
  },
  {
    value: "lppls",
    label: "Break date",
    note: "A date for a break, when that fit exists.",
  },
  {
    value: "sentiment",
    label: "News tone",
    note: "News tone, when headlines exist.",
  },
] as const;

export function EvidencePanel({ fullSpan = false }: { fullSpan?: boolean }) {
  const [tab, setTab] = useState<(typeof TABS)[number]["value"]>("score");
  const base = TABS.find((item) => item.value === tab)?.note ?? "";
  const note =
    fullSpan && tab === "score"
      ? "Heat for this book across the whole history. Quiet is under 40. Warming starts at 40. Stretched starts at 70."
      : fullSpan && tab === "bsadf"
        ? "The fast rise across the whole history, against the ordinary line. A reading far above that line is drawn at the top of the chart."
        : base;

  return (
    <Tabs.Root
      className="evidence-panel"
      value={tab}
      onValueChange={(value) =>
        setTab(value as (typeof TABS)[number]["value"])
      }
    >
      <Tabs.List className="evidence-tabs" aria-label="Charts for this book">
        {TABS.map((item) => (
          <Tabs.Trigger key={item.value} value={item.value}>
            {item.label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      <p className="evidence-note">{note}</p>
      <div className="evidence-body">
        <Tabs.Content value="score">
          <ScoreChart fullSpan={fullSpan} />
        </Tabs.Content>
        <Tabs.Content value="bsadf">
          <BSADFChart fullSpan={fullSpan} />
        </Tabs.Content>
        <Tabs.Content value="lppls">
          <LPPLSChart fullSpan={fullSpan} />
        </Tabs.Content>
        <Tabs.Content value="sentiment">
          <SentimentChart fullSpan={fullSpan} />
        </Tabs.Content>
      </div>
    </Tabs.Root>
  );
}
