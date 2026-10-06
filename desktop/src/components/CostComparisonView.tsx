import React, { useState, useEffect } from "react";
import { Layers, Wallet, AlertTriangle } from "lucide-react";
import { CostComparisonResult, SplitOrderResult } from "../types";
import { api } from "../ipc";

export const CostComparisonView: React.FC = () => {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [amount, setAmount] = useState("1000.00");
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [results, setResults] = useState<CostComparisonResult[]>([]);
  const [gridData, setGridData] = useState<Record<string, CostComparisonResult[]>>({});
  const [splitResult, setSplitResult] = useState<SplitOrderResult | null>(null);
  const [userBalance, setUserBalance] = useState<string>("");
  const [splitRatio, setSplitRatio] = useState<number>(50); // 50% / 50%
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const runComparison = async () => {
    try {
      setErrorMsg(null);
      const res = await api.compareCosts(side, amount, symbol, splitRatio);
      setResults(res.results || []);
      if (res.grid) setGridData(res.grid);
      if (res.split !== undefined) setSplitResult(res.split);
    } catch (err: any) {
      setErrorMsg(err.message || String(err));
      setResults([]);
    }
  };

  useEffect(() => {
    runComparison();
  }, [side, amount, symbol, splitRatio]);

  const parsedBal = parseFloat(userBalance);
  const parsedAmt = parseFloat(amount) || 0;
  const isBalanceProvided = !isNaN(parsedBal) && userBalance.trim() !== "";
  const isFeasible = isBalanceProvided ? parsedBal >= parsedAmt : null;

  return (
    <section aria-labelledby="cost-title">
      <div className="panel-header">
        <h2 id="cost-title" className="panel-title">Personal Execution Cost Comparison & Scenarios</h2>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className={`btn btn-sm ${side === "buy" ? "btn-primary" : ""}`}
            onClick={() => setSide("buy")}
          >
            Buy (Quote Budget)
          </button>
          <button
            className={`btn btn-sm ${side === "sell" ? "btn-primary" : ""}`}
            onClick={() => setSide("sell")}
          >
            Sell (Base Quantity)
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="panel-card" style={{ marginBottom: 12, borderColor: "var(--color-danger)", color: "var(--color-danger)" }}>
          <AlertTriangle size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
          <strong>Cost Comparison Error:</strong> {errorMsg}
        </div>
      )}

      <div className="grid-3">
        <article className="panel-card">
          <div className="form-group">
            <label className="form-label" htmlFor="cost-amount">
              {side === "buy" ? "All-In Quote Budget" : "Base Amount to Sell"}
            </label>
            <input
              id="cost-amount"
              type="text"
              className="form-input"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="cost-symbol">Spot Instrument</label>
            <select
              id="cost-symbol"
              className="form-select"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            >
              <option value="BTC/USDT">BTC/USDT</option>
              <option value="ETH/USDT">ETH/USDT</option>
            </select>
          </div>
        </article>

        <article className="panel-card">
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <Wallet size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
            User Inventory Feasibility
          </h3>
          <div className="form-group">
            <label className="form-label" htmlFor="cost-balance">Available Balance (Optional)</label>
            <input
              id="cost-balance"
              type="text"
              className="form-input"
              placeholder="e.g. 5000 USDT (leave blank for unconstrained)"
              value={userBalance}
              onChange={(e) => setUserBalance(e.target.value)}
            />
          </div>
          <div style={{ fontSize: 11, marginTop: 4 }}>
            Status:{" "}
            {!isBalanceProvided ? (
              <span className="badge badge-neutral">UNKNOWN (UNCONSTRAINED)</span>
            ) : isFeasible ? (
              <span className="badge badge-success">FEASIBLE (NO SHORTFALL)</span>
            ) : (
              <span className="badge badge-danger">
                INSUFFICIENT (SHORTFALL: {(parsedAmt - parsedBal).toFixed(2)})
              </span>
            )}
          </div>
        </article>

        <article className="panel-card">
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
            <Layers size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
            Split-Order Scenario (Disjoint Depth)
          </h3>
          <div style={{ fontSize: 12, marginBottom: 6 }}>
            Coinbase: {splitRatio}% | Kraken: {100 - splitRatio}%
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={splitRatio}
            onChange={(e) => setSplitRatio(parseInt(e.target.value, 10))}
            style={{ width: "100%", marginBottom: 8 }}
          />
          {splitResult && (
            <div style={{ fontSize: 11, background: "var(--bg-subtle)", padding: 6, borderRadius: 4, marginBottom: 4 }}>
              <div>
                <strong>Combined Outcome: </strong>
                {side === "buy" ? `${splitResult.total_base} base` : `$${splitResult.total_spent_or_received} quote`}
                {" "}@ avg ${splitResult.effective_avg_price}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                <span>Total Child Fees: ${splitResult.total_fees_quote}</span>
                <span className={`badge ${splitResult.all_complete ? "badge-success" : "badge-danger"}`}>
                  {splitResult.all_complete ? "CONSERVED & COMPLETE" : "DEPTH EXHAUSTED"}
                </span>
              </div>
            </div>
          )}
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
            Applies fixed order fees at the child-order level and consumes disjoint depth.
          </div>
        </article>
      </div>

      <div className="panel-card" style={{ marginTop: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
          Venue Execution Ranking ({side.toUpperCase()} {amount} {symbol})
        </h3>
        <div className="table-container">
          <table className="compact-table">
            <thead>
              <tr>
                <th>Rank & Venue</th>
                <th>{side === "buy" ? "Net Acquired Base" : "Net Quote Proceeds"}</th>
                <th>VWAP Avg Price</th>
                <th>Taker Fee (Quote)</th>
                <th>Taker Fee (Base)</th>
                <th>Total Outlay / Result</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, idx) => (
                <tr key={r.venue}>
                  <td>
                    <span style={{ fontWeight: 600, marginRight: 6 }}>#{idx + 1}</span>
                    <span style={{ textTransform: "capitalize" }}>{r.venue}</span>
                  </td>
                  <td className="num-cell" style={{ fontWeight: 600, color: "var(--color-primary)" }}>
                    {side === "buy" ? `${r.acquired_base} BTC` : `$${r.net_proceeds}`}
                  </td>
                  <td className="num-cell">${r.avg_price}</td>
                  <td className="num-cell">${r.fee_quote}</td>
                  <td className="num-cell">{r.fee_base}</td>
                  <td className="num-cell">
                    {side === "buy" ? `$${r.total_cost}` : `$${r.net_proceeds}`}
                  </td>
                  <td>
                    {r.is_complete ? (
                      <span className="badge badge-success">COMPLETE</span>
                    ) : (
                      <span className="badge badge-danger">{r.rejection_reason || "INCOMPLETE"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel-card" style={{ marginTop: 12 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Amount Sensitivity Grid</h3>
        <div className="grid-3">
          {["100.00", "1000.00", "10000.00"].map((gridAmt) => {
            const rowResults = gridData[gridAmt] || [];
            const topCandidate = rowResults.find((r) => r.is_complete) || rowResults[0];
            const isUsable = topCandidate ? topCandidate.is_complete : false;
            const cheapestText = topCandidate
              ? isUsable
                ? `${topCandidate.venue.toUpperCase()} ($${topCandidate.avg_price})`
                : "None (Insufficient depth)"
              : "Calculating...";
            return (
              <div
                key={gridAmt}
                style={{
                  border: "1px solid var(--border-color)",
                  padding: 10,
                  borderRadius: "var(--radius)",
                  backgroundColor: "var(--bg-subtle)",
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>
                  Size: {gridAmt} {side === "buy" ? "USDT" : "BTC"}
                </div>
                <div style={{ fontSize: 11, display: "flex", justifyContent: "space-between" }}>
                  <span>Cheapest Venue:</span>
                  <span style={{ fontWeight: 600 }}>{cheapestText}</span>
                </div>
                <div style={{ fontSize: 11, display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                  <span>Depth Coverage:</span>
                  <span className={`badge ${isUsable ? "badge-success" : "badge-danger"}`}>
                    {isUsable ? "USABLE" : (topCandidate?.rejection_reason || "INSUFFICIENT_DEPTH")}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
