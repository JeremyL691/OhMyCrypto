import React, { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { OverviewView } from "./components/OverviewView";
import { OpportunitiesView } from "./components/OpportunitiesView";
import { DiagnosticsView } from "./components/DiagnosticsView";
import { CostComparisonView } from "./components/CostComparisonView";
import { SettingsView } from "./components/SettingsView";
import { ReplayModal } from "./components/ReplayModal";
import { EngineStatus, IncidentItem, OpportunityItem, TabKey } from "./types";
import { api } from "./ipc";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [theme, setTheme] = useState<"light" | "dark">(
    (localStorage.getItem("theme") as "light" | "dark") ||
      (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light")
  );
  const [status, setStatus] = useState<EngineStatus>({
    status: "idle",
    uptime_sec: 0,
    pid: 0,
    active_symbol: "BTC/USDT",
    active_budget: "1000.00",
    is_demo: true,
  });
  const [opportunities, setOpportunities] = useState<OpportunityItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [replayItem, setReplayItem] = useState<OpportunityItem | null>(null);

  const loadData = async () => {
    try {
      const [s, opps, incs] = await Promise.all([
        api.getStatus(),
        api.getOpportunities(),
        api.getIncidents(),
      ]);
      setStatus(s);
      setOpportunities(opps);
      setIncidents(incs);
    } catch (err) {
      console.error("Failed to load data:", err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-container" data-theme={theme}>
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        theme={theme}
        setTheme={setTheme}
        isMonitoring={status.status === "monitoring"}
      />

      <main className="main-content">
        {status.is_demo && (
          <aside className="demo-banner" role="status">
            <span>
              <strong>OFFLINE DEMO / FIXTURE MODE:</strong> Real-time engine sidecar disconnected. Displaying verified local fixture dataset.
            </span>
          </aside>
        )}

        {activeTab === "overview" && (
          <OverviewView
            status={status}
            opportunities={opportunities}
            onRefresh={loadData}
          />
        )}

        {activeTab === "opportunities" && (
          <OpportunitiesView
            opportunities={opportunities}
            onOpenReplay={(item) => setReplayItem(item)}
          />
        )}

        {activeTab === "diagnostics" && (
          <DiagnosticsView incidents={incidents} onRefresh={loadData} />
        )}

        {activeTab === "cost" && <CostComparisonView />}

        {activeTab === "settings" && <SettingsView />}
      </main>

      {replayItem && (
        <ReplayModal item={replayItem} onClose={() => setReplayItem(null)} />
      )}
    </div>
  );
};
export default App;
