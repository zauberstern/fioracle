import * as Tooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";
import { glossary, type GlossaryKey } from "../../copy/glossary";

type HintProps = {
  entry: GlossaryKey;
  children: ReactNode;
  extra?: string;
  side?: "top" | "right" | "bottom" | "left";
};

export function HintProvider({ children }: { children: ReactNode }) {
  return (
    <Tooltip.Provider delayDuration={200} skipDelayDuration={100}>
      {children}
    </Tooltip.Provider>
  );
}

export function Hint({ entry, children, extra, side = "top" }: HintProps) {
  const item = glossary[entry];
  const body = extra ? `${item.tech} ${extra}` : item.tech;

  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span className="hint-trigger" tabIndex={0}>
          {children}
        </span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="hint-content" side={side} sideOffset={6}>
          <div className="hint-label">{item.label}</div>
          <div className="hint-tech">{body}</div>
          <Tooltip.Arrow className="hint-arrow" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export function HintLabel({ entry }: { entry: GlossaryKey }) {
  return <Hint entry={entry}>{glossary[entry].label}</Hint>;
}
