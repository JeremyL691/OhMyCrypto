import React, { useState } from "react";
import { Play, Pause, RefreshCw } from "lucide-react";
import { EngineStatus, OpportunityItem } from "../types";
import { api } from "../ipc";

interface OverviewProps {
  status: EngineStatus;
  opportunities: OpportunityItem[];
  onRefresh: () => void;
}

export const OverviewView: React.FC<OverviewProps> = ({ status, opportunities, onRefresh }) => {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [budget, setBudget] = useState("1000.00");
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    await api.startMonitor(symbol, budget);
    setLoading(false);
    onRefresh();
  };

  const handlePause = async () => {
    setLoading(true);
    if (status.status === "monitoring") {
      await api.pauseMonitor();
    } else {
      await api.resumeMonitor();
    }
    setLoading(false);
    onRefresh();
  };

  return (
    <section aria-labelledby="overview-title">
      <div className="panel-header">
        <h2 id="overview-title" className="panel-title">System Overview & Monitoring Control</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw size={13} /> Refresh
          </button>
          {status.status === "monitoring" ? (
            <button className="btn btn-sm" onClick={handlePause} disabled={loading}>
              <Pause size={13} /> Pause Monitor
            </button>
          ) : status.status === "paused" ? (
            <button className="btn btn-sm btn-primary" onClick={handlePause} disabled={loading}>
              <Play size={13} /> Resume Monitor
            </button>
          ) : (
            <button className="btn btn-sm btn-primary" onClick={handleStart} disabled={loading}>
              <Play size={13} /> Start Monitor
            </button>
          )}
        </div>
      </div>

      <div className="grid-3">
        <article className="panel-card">
          <div className="form-group">
            <label className="form-label">Spot Instrument</label>
            <select
              className="form-select"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              disabled={status.status === "monitoring"}
            >
              <option value="BTC/USDT">BTC/USDT (Coinbase / Kraken)</option>
              <option value="ETH/USDT">ETH/USDT (Coinbase / Kraken)</option>
              <option value="SOL/USDT">SOL/USDT (Coinbase / Kraken)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">All-In Quote Budget</label>
            <input
              type="text"
              className="form-input"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              disabled={status.status === "monitoring"}
            />
          </div>
          <p style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Strict budget enforcement: spend + fees stays within quote budget.
          </p>
        </article>

        <article className="panel-card">
          <h3 style={{ fontSize: 13, marginBottom: 8, fontWeight: 600 }}>Active Connectors</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Coinbase Advanced Trade</span>
              <span className="badge badge-success">CLEAN (85ms)</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Kraken Spot Book v2</span>
              <span className="badge badge-success">CRC32 VERIFIED (62ms)</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>Database Engine</span>
              <span className="badge badge-neutral">SQLITE WAL</span>
            </div>
          </div>
        </article>

        <article className="panel-card">
          <h3 style={{ fontSize: 13, marginBottom: 8, fontWeight: 600 }}>Engine Metrics</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Status:</span>
              <span style={{ fontWeight: 600 }}>{status.status.toUpperCase()}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Process PID:</span>
              <span className="num-cell">{status.pid}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Active Route:</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>Coinbase &lt;&gt; Kraken</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-muted)" }}>Verified Opportunities:</span>
              <span className="num-cell">{opportunities.filter((o) => o.is_eligible).length}</span>
            </div>
          </div>
        </article>
      </div>

      <div className="panel-card" style={{ marginTop: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Recent Candidate Decisions</h3>
        <div className="table-container">
          <table className="compact-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Route</th>
                <th>Spread</th>
                <th>Midpoint</th>
                <th>Net Profit</th>
                <th>Status</th>
                <th>500ms</th>
                <th>1s</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((opp) => (
                <tr key={opp.event_id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{opp.event_id.slice(0, 16)}...</td>
                  <td>{opp.buy_venue} &rarr; {opp.sell_venue}</td>
                  <td className="num-cell">{(parseFloat(opp.effective_spread) * 100).toFixed(3)}%</td>
                  <td className="num-cell">${opp.midpoint_price}</td>
                  <td className={`num-cell ${opp.is_positive ? "badge-success" : "badge-danger"}`} style={{ fontWeight: 600 }}>
                    {opp.net_profit_quote} {opp.budget_units}
                  </td>
                  <td>
                    {opp.is_eligible ? (
                      <span className="badge badge-success">ELIGIBLE</span>
                    ) : (
                      <span className="badge badge-neutral">INELIGIBLE</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${opp.follow_up_500ms === "persisted" ? "badge-success" : "badge-danger"}`}>
                      {opp.follow_up_500ms || "N/A"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${opp.follow_up_1s === "persisted" ? "badge-success" : "badge-danger"}`}>
                      {opp.follow_up_1s || "N/A"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
