import { useCallback, useEffect, useState } from "react";
import { WeeklyReading } from "../reading/WeeklyReading";
import { CloserView } from "../reading/CloserView";
import { ThenView } from "../reading/ThenView";
import { DiagnosticsView } from "../reading/DiagnosticsView";
import { PitchView } from "../reading/PitchView";
import { GameEmbed } from "../game/GameEmbed";
import { HintProvider } from "../ui/Hint";
import { useMarketStore } from "../../store/marketStore";
import { useHistoryTape } from "../../hooks/useHistoryTape";
import { useWebSocket } from "../../hooks/useWebSocket";
import { readPin } from "../../shell/readPin";
import meridianLogo from "../../assets/meridian-logo.png";

const NAV: Array<{ view: ReadingView; label: string }> = [
  { view: "about", label: "How it works" },
  { view: "closer", label: "Look closer" },
  { view: "then", label: "History" },
  { view: "diagnostics", label: "Diagnostics" },
  { view: "stillmoor", label: "Stillmoor" },
];

const DEFAULT_AS_OF = "2008-09-15";

export type ReadingView =
  | "home"
  | "closer"
  | "then"
  | "stillmoor"
  | "diagnostics"
  | "about";

function parseHash(hash: string): ReadingView {
  const h = hash.replace(/^#\/?/, "").split("?")[0].toLowerCase();
  if (h === "closer") return "closer";
  if (h === "then") return "then";
  if (h === "stillmoor") return "stillmoor";
  if (h === "diagnostics") return "diagnostics";
  if (h === "about") return "about";
  return "home";
}

function hashFor(view: ReadingView): string {
  if (view === "home") return "#/";
  return `#/${view}`;
}

export function AppShell() {
  const asset = useMarketStore((s) => s.currentAsset);
  useHistoryTape(asset);
  useWebSocket({ asset, autoReconnect: true });

  const [view, setView] = useState<ReadingView>(() =>
    typeof window !== "undefined" ? parseHash(window.location.hash) : "home"
  );

  useEffect(() => {
    const pin = readPin(window.location.hash);
    const asOf = pin.asof || DEFAULT_AS_OF;
    useMarketStore.getState().setReplayTimestamp(Date.parse(`${asOf}T00:00:00Z`) / 1000);
    if (pin.book) {
      useMarketStore.getState().setCurrentAsset(pin.book);
    }
  }, []);

  useEffect(() => {
    const onHash = () => setView(parseHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = useCallback((next: ReadingView | string) => {
    const v =
      typeof next === "string"
        ? parseHash(next.startsWith("#") ? next : `#/${next}`)
        : next;
    const target = hashFor(v);
    if (window.location.hash !== target) {
      window.location.hash = target;
    } else {
      setView(v);
    }
  }, []);

  return (
    <HintProvider>
      <div className="app-shell reading-shell">
        {view === "stillmoor" ? null : (
          <header className="reading-header">
            <button
              type="button"
              className="reading-brand"
              onClick={() => navigate("home")}
            >
              <img src={meridianLogo} alt="" />
              Meridian
            </button>
            <nav className="reading-nav" aria-label="Sections">
              {NAV.map((item) => (
                <button
                  key={item.view}
                  type="button"
                  aria-current={view === item.view ? "page" : undefined}
                  onClick={() => navigate(item.view)}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </header>
        )}
        <div
          className={
            view === "diagnostics"
              ? "app-shell-body reading-body reading-body-lock"
              : "app-shell-body reading-body"
          }
        >
          {view === "home" ? <WeeklyReading /> : null}
          {view === "closer" ? <CloserView /> : null}
          {view === "then" ? (
            <ThenView onBack={() => navigate("home")} />
          ) : null}
          {view === "diagnostics" ? <DiagnosticsView /> : null}
          {view === "about" ? <PitchView /> : null}
          {view === "stillmoor" ? (
            <div className="stillmoor-view">
              <header className="stillmoor-chrome">
                <button
                  type="button"
                  className="reading-back"
                  onClick={() => navigate("home")}
                >
                  Back to this week
                </button>
                <span className="stillmoor-construction">Under construction</span>
              </header>
              <GameEmbed />
            </div>
          ) : null}
        </div>
      </div>
    </HintProvider>
  );
}
