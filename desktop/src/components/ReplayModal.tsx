import React, { useState } from "react";
import { X, Play, CheckCircle2 } from "lucide-react";
import { OpportunityItem } from "../types";
import { api } from "../ipc";

interface ReplayModalProps {
  item: OpportunityItem;
  onClose: () => void;
}

export const ReplayModal: React.FC<ReplayModalProps> = ({ item, onClose }) => {
  const [overrideFee, setOverrideFee] = useState<string>("");
  const [replayResult, setReplayResult] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const handleRunReplay = async () => {
    setRunning(true);
    try {
      const res = await api.replayEvent(item.event_id, overrideFee.trim() ? overrideFee.trim() : undefined);
      const actualResult = res?.replay || res;
      setReplayResult(actualResult);
    } catch (err) {
      console.error("Replay failed:", err);
    } finally {
      setRunning(false);
    }
  };

  const baseToken = item.symbol ? item.symbol.split("/")[0] : "Base";
  const quoteToken = item.symbol ? (item.symbol.split("/")[1] || "Quote") : "Quote";

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="replay-title">
      <div className="modal-dialog">
        <div className="panel-header">
          <h3 id="replay-title" className="panel-title">
            Deterministic Event Replay & Inspection
          </h3>
          <button className="btn btn-sm" onClick={onClose} aria-label="Close dialog">
            <X size={14} />
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-muted)" }}>Event ID:</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{item.event_id}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-muted)" }}>Route:</span>
            <span style={{ fontWeight: 600 }}>{item.route_key}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-muted)" }}>Input Hash (SHA-256):</span>
            {item.input_hash ? (
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{item.input_hash.slice(0, 24)}...</span>
            ) : (
              <span style={{ color: "var(--text-muted)", fontStyle: "italic", fontSize: 11 }}>Legacy Record (No Hash)</span>
            )}
          </div>

          <div className="grid-2" style={{ marginTop: 8 }}>
            <div style={{ padding: 8, backgroundColor: "var(--bg-subtle)", borderRadius: "var(--radius)" }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Buy Leg ({item.buy_venue})</div>
              <div>Spent: ${item.buy_fill?.quote_spent ?? item.buy_fill?.spent_quote ?? "0.00"}</div>
              <div>Fee: ${item.buy_fill?.fee_quote ?? item.buy_fill?.fee_paid ?? "0.00"}</div>
              <div>Acquired: {item.buy_fill?.acquired_base ?? "0"} {baseToken}</div>
              <div>VWAP: ${item.buy_fill?.avg_price ?? item.buy_fill?.effective_avg_price ?? "0.00"}</div>
            </div>

            <div style={{ padding: 8, backgroundColor: "var(--bg-subtle)", borderRadius: "var(--radius)" }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Sell Leg ({item.sell_venue})</div>
              <div>Proceeds: ${item.sell_fill?.quote_received ?? item.sell_fill?.proceeds_quote ?? "0.00"}</div>
              <div>Fee: ${item.sell_fill?.fee_quote ?? item.sell_fill?.fee_paid ?? "0.00"}</div>
              <div>Sold: {item.sell_fill?.acquired_base ?? item.buy_fill?.acquired_base ?? "0"} {baseToken}</div>
              <div>VWAP: ${item.sell_fill?.avg_price ?? item.sell_fill?.effective_avg_price ?? "0.00"}</div>
            </div>
          </div>

          <div style={{ marginTop: 8, padding: 8, border: "1px solid var(--border-color)", borderRadius: "var(--radius)" }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>Replay Parameter Override (Simulation)</div>
            <div className="form-group">
              <label className="form-label">Taker Fee Rate (optional)</label>
              <input
                type="text"
                className="form-input"
                placeholder="Leave blank to verify original recorded fees"
                value={overrideFee}
                onChange={(e) => setOverrideFee(e.target.value)}
              />
            </div>
            <button className="btn btn-sm btn-primary" onClick={handleRunReplay} disabled={running}>
              <Play size={12} /> Run Deterministic Replay
            </button>
          </div>

          {replayResult && (
            <div
              style={{
                marginTop: 6,
                padding: 10,
                borderRadius: "var(--radius)",
                backgroundColor: replayResult.is_exact_match ? "rgba(34, 197, 94, 0.1)" : "var(--bg-highlight)",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                {replayResult.is_exact_match ? (
                  <span style={{ color: "var(--color-success)" }}>
                    <CheckCircle2 size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                    Exact Bit-Identical Hash Match
                  </span>
                ) : (
                  <span>Replay Result Under Modified Fee Profile:</span>
                )}
              </div>
              <div>Original Profit: {replayResult.original_profit ?? replayResult.original_profit_quote ?? "0.00"} {quoteToken}</div>
              <div>Replayed Profit: {replayResult.replayed_profit ?? replayResult.replayed_profit_quote ?? "0.00"} {quoteToken}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
