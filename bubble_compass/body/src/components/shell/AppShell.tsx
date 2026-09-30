import { Group, Panel, Separator } from "react-resizable-panels";
import * as Tabs from "@radix-ui/react-tabs";
import { TopBar } from "../dashboard/TopBar";
import { Dashboard, LeftRail } from "../dashboard/Dashboard";
import { WorldCanvas } from "../../world/WorldCanvas";
import { GameEmbed } from "../game/GameEmbed";
import { CrisisAlert } from "./CrisisAlert";
import { glossary } from "../../copy/glossary";
import { Hint, HintProvider } from "../ui/Hint";
import { useMarketStore } from "../../store/marketStore";
import { useHistoryTape } from "../../hooks/useHistoryTape";
import { useWebSocket } from "../../hooks/useWebSocket";

export function AppShell() {
  const asset = useMarketStore((s) => s.currentAsset);
  const enableWorld3d = useMarketStore((s) => s.enableWorld3d);
  useHistoryTape(asset);
  useWebSocket({ asset, autoReconnect: true });

  return (
    <HintProvider>
      <div className="app-shell">
        <TopBar />
        <CrisisAlert />
        <div className="app-shell-body">
          <Group orientation="horizontal" style={{ height: "100%" }}>
            <Panel id="rail" defaultSize="20" minSize="15" maxSize="28">
              <LeftRail />
            </Panel>
            <Separator className="resize-handle" />
            <Panel id="main" defaultSize="80" minSize="50">
              <Tabs.Root className="main-tabs" defaultValue="dashboard">
                <Tabs.List className="tab-list" aria-label="Primary views">
                  <Tabs.Trigger value="dashboard">
                    <Hint entry="overview">{glossary.overview.label}</Hint>
                  </Tabs.Trigger>
                  <Tabs.Trigger value="game">
                    <Hint entry="game">{glossary.game.label}</Hint>
                  </Tabs.Trigger>
                  {enableWorld3d ? (
                    <Tabs.Trigger value="world">
                      <Hint entry="world">
                        {glossary.world.label}{" "}
                        <span className="tab-sub">(flagged)</span>
                      </Hint>
                    </Tabs.Trigger>
                  ) : null}
                </Tabs.List>
                <Tabs.Content value="dashboard" className="tab-content">
                  <Dashboard />
                </Tabs.Content>
                <Tabs.Content value="game" className="tab-content">
                  <GameEmbed />
                </Tabs.Content>
                {enableWorld3d ? (
                  <Tabs.Content value="world" className="tab-content">
                    <WorldCanvas />
                  </Tabs.Content>
                ) : null}
              </Tabs.Root>
            </Panel>
          </Group>
        </div>
      </div>
    </HintProvider>
  );
}
