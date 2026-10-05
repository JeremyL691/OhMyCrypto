import React, { useState } from "react";
import { FileCode } from "lucide-react";
import { OpportunityItem } from "../types";

interface OpportunitiesProps {
  opportunities: OpportunityItem[];
  onOpenReplay: (item: OpportunityItem) => void;
}

export const OpportunitiesView: React.FC<OpportunitiesProps> = ({ opportunities, onOpenReplay }) => {
  const [filter, setFilter] = useState<"all" | "eligible" | "ineligible">("all");

  const filtered = opportunities.filter((item) => {
    if (filter === "eligible") return item.is_eligible;
    if (filter === "ineligible") return !item.is_eligible;
    return true;
  });

  return (
    <section aria-labelledby="opportunities-title">
      <div className="panel-header">
        <h2 id="opportunities-title" className="panel-title">Opportunity Verification & Evidence Inspection</h2>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className={`btn btn-sm ${filter === "all" ? "btn-primary" : ""}`}
            onClick={() => setFilter("all")}
          >
            All ({opportunities.length})
          </button>
          <button
            className={`btn btn-sm ${filter === "eligible" ? "btn-primary" : ""}`}
            onClick={() => setFilter("eligible")}
          >
            Eligible ({opportunities.filter((o) => o.is_eligible).length})
          </button>
          <button
            className={`btn btn-sm ${filter === "ineligible" ? "btn-primary" : ""}`}
            onClick={() => setFilter("ineligible")}
          >
            Ineligible ({opportunities.filter((o) => !o.is_eligible).length})
          </button>
        </div>
      </div>

      <div className="panel-card">
        <div className="table-container">
          <table className="compact-table">
            <thead>
              <tr>
                <th>Event & Episode</th>
                <th>Route</th>
                <th>Budget</th>
                <th>Acquired Base</th>
                <th>Net Profit</th>
                <th>Spread</th>
                <th>Continuous</th>
                <th>500ms</th>
                <th>1s</th>
                <th>3s</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((opp) => (
                <tr key={opp.event_id}>
                  <td>
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 600 }}>
                      {opp.event_id.slice(0, 18)}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                      {opp.episode_id}
                    </div>
                  </td>
                  <td>
                    <span style={{ fontWeight: 500 }}>{opp.symbol}</span>
                    <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      {opp.buy_venue} &rarr; {opp.sell_venue}
                    </div>
                  </td>
                  <td className="num-cell">
                    {opp.budget_amount} {opp.budget_units}
                  </td>
                  <td className="num-cell" style={{ fontFamily: "var(--font-mono)" }}>
                    {opp.buy_fill.acquired_base}
                  </td>
                  <td className={`num-cell ${opp.is_positive ? "badge-success" : "badge-danger"}`} style={{ fontWeight: 600 }}>
                    {opp.net_profit_quote} {opp.budget_units}
                  </td>
                  <td className="num-cell">
                    {(parseFloat(opp.effective_spread) * 100).toFixed(3)}%
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        opp.continuous_persistence_status === "continuous"
                          ? "badge-success"
                          : "badge-danger"
                      }`}
                    >
                      {opp.continuous_persistence_status || "UNKNOWN"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${opp.follow_up_500ms === "persisted" ? "badge-success" : "badge-neutral"}`}>
                      {opp.follow_up_500ms || "N/A"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${opp.follow_up_1s === "persisted" ? "badge-success" : "badge-neutral"}`}>
                      {opp.follow_up_1s || "N/A"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${opp.follow_up_3s === "persisted" ? "badge-success" : "badge-neutral"}`}>
                      {opp.follow_up_3s || "N/A"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-sm"
                      onClick={() => onOpenReplay(opp)}
                      title="Inspect fill calculation and run deterministic replay"
                    >
                      <FileCode size={12} /> Inspect / Replay
                    </button>
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
