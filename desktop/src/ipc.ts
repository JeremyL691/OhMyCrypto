import { invoke } from "@tauri-apps/api/core";
import { CostComparisonResult, EngineStatus, IncidentItem, OpportunityItem } from "./types";

const IS_TAURI = typeof window !== "undefined" && Boolean((window as any).__TAURI_INTERNALS__);

// Realistic fixture dataset explicitly labeled as demo/fixture. It is ONLY
// used when the real engine sidecar is unreachable (browser dev server,
// sidecar failure) so recorded evidence is never faked by fixtures.
const FIXTURE_OPPORTUNITIES: OpportunityItem[] = [
  {
    event_id: "evt_1728148800000_6b82d858",
    episode_id: "ep_1_1728148800000",
    route_key: "coinbase->kraken:BTC/USDT:1000USDT",
    timestamp_utc_ms: 1728148800000,
    symbol: "BTC/USDT",
    buy_venue: "coinbase",
    sell_venue: "kraken",
    budget_amount: "1000.00",
    budget_units: "USDT",
    net_profit_quote: "3.42",
    effective_spread: "0.00342",
    midpoint_price: "85700.00",
    is_positive: true,
    is_eligible: true,
    eligibility_reasons: [],
    input_hash: "57d6a83e683b0c268d44ae04abc12f262bf8fb991ef7c311456f19eb49666399",
    config_hash: "9af8c2847c1b54a23b118da571ef99480cfca2a868f121d5c5890e1c6b840131",
    follow_up_500ms: "persisted",
    follow_up_1s: "persisted",
    follow_up_3s: "persisted",
    continuous_persistence_status: "continuous",
    notification_state: "delivered",
    buy_fill: {
      side: "buy",
      requested_amount: "1000.00",
      acquired_base: "0.01163400",
      quote_spent: "997.50",
      quote_received: "0.00",
      avg_price: "85739.21",
      fee_quote: "2.49",
      fee_base: "0.00",
      residual_quote: "0.01",
      residual_base: "0.00",
      levels_consumed: 1,
      is_complete: true,
    },
    sell_fill: {
      side: "sell",
      requested_amount: "0.01163400",
      acquired_base: "0.00",
      quote_spent: "0.00",
      quote_received: "1000.92",
      avg_price: "86034.03",
      fee_quote: "2.51",
      fee_base: "0.00",
      residual_quote: "0.00",
      residual_base: "0.00",
      levels_consumed: 1,
      is_complete: true,
    },
  },
  {
    event_id: "evt_1728148830000_2f8a11bc",
    episode_id: "ep_2_1728148830000",
    route_key: "kraken->coinbase:ETH/USDT:1000USDT",
    timestamp_utc_ms: 1728148830000,
    symbol: "ETH/USDT",
    buy_venue: "kraken",
    sell_venue: "coinbase",
    budget_amount: "1000.00",
    budget_units: "USDT",
    net_profit_quote: "-1.85",
    effective_spread: "-0.00185",
    midpoint_price: "2820.00",
    is_positive: false,
    is_eligible: false,
    eligibility_reasons: ["non_positive_profit"],
    input_hash: "2f8a11bc19e34270c5e6381ab4859a016b84013157d6a83e683b0c268d44ae04",
    config_hash: "9af8c2847c1b54a23b118da571ef99480cfca2a868f121d5c5890e1c6b840131",
    follow_up_500ms: "failed",
    follow_up_1s: "failed",
    continuous_persistence_status: "interrupted",
    notification_state: "suppressed",
    buy_fill: {
      side: "buy",
      requested_amount: "1000.00",
      acquired_base: "0.3537",
      quote_spent: "997.50",
      quote_received: "0.00",
      avg_price: "2820.18",
      fee_quote: "2.49",
      fee_base: "0.00",
      residual_quote: "0.01",
      residual_base: "0.00",
      levels_consumed: 1,
      is_complete: true,
    },
    sell_fill: {
      side: "sell",
      requested_amount: "0.3537",
      acquired_base: "0.00",
      quote_spent: "0.00",
      quote_received: "995.65",
      avg_price: "2815.00",
      fee_quote: "2.49",
      fee_base: "0.00",
      residual_quote: "0.00",
      residual_base: "0.00",
      levels_consumed: 1,
      is_complete: true,
    },
  },
];

const FIXTURE_INCIDENTS: IncidentItem[] = [
  {
    incident_id: "inc_1_1728148810000",
    connector: "kraken",
    channel: "book_v2",
    fault_class: "sequence_gap",
    trigger: "Sequence jump from 104 to 106",
    severity: "error",
    opened_at_ms: 1728148810000,
    closed_at_ms: 1728148815000,
    is_recovered: true,
    raw_evidence: { expected: 105, received: 106, recovery_action: "rest_snapshot_resync" },
  },
  {
    incident_id: "inc_2_1728148840000",
    connector: "coinbase",
    channel: "rest_l2",
    fault_class: "consecutive_failures",
    trigger: "3 consecutive 503 gateway timeouts",
    severity: "error",
    opened_at_ms: 1728148840000,
    is_recovered: false,
    raw_evidence: { consecutive_count: 3, last_http_status: 503 },
  },
];

// Real sidecar call over the Tauri IPC bridge. The shell forwards the action
// verbatim to the packaged Python sidecar over JSON Lines stdin/stdout.
async function sidecarCall<T>(action: string, payload: Record<string, unknown> = {}): Promise<T> {
  if (!IS_TAURI) throw new Error("sidecar unavailable outside the native shell");
  return await invoke<T>("sidecar_request", { action, payload });
}

export const api = {
  async getStatus(): Promise<EngineStatus> {
    if (IS_TAURI) {
      try {
        return await sidecarCall<EngineStatus>("get_status");
      } catch (err) {
        // In native mode, if status call fails, throw so App handles error visibly
        throw err;
      }
    }
    return {
      status: "idle",
      uptime_sec: 0,
      pid: 0,
      active_symbol: "BTC/USDT",
      active_budget: "1000.00",
      is_demo: true,
    };
  },

  async startMonitor(symbol: string, budget: string): Promise<EngineStatus> {
    if (IS_TAURI) {
      return await sidecarCall<EngineStatus>("start_monitor", { symbol, budget });
    }
    throw new Error("Engine sidecar unavailable; monitoring requires the installed application.");
  },

  async pauseMonitor(): Promise<EngineStatus> {
    return sidecarCall<EngineStatus>("pause_monitor");
  },

  async resumeMonitor(): Promise<EngineStatus> {
    return sidecarCall<EngineStatus>("resume_monitor");
  },

  async stopMonitor(): Promise<EngineStatus> {
    return sidecarCall<EngineStatus>("stop_monitor");
  },

  async getOpportunities(): Promise<OpportunityItem[]> {
    if (IS_TAURI) {
      const res = await sidecarCall<{ opportunities: OpportunityItem[] }>("get_opportunities", { limit: 50 });
      return res.opportunities;
    }
    return [...FIXTURE_OPPORTUNITIES];
  },

  async getIncidents(): Promise<IncidentItem[]> {
    if (IS_TAURI) {
      const res = await sidecarCall<{ incidents: IncidentItem[] }>("get_incidents", { limit: 50 });
      return res.incidents;
    }
    return [...FIXTURE_INCIDENTS];
  },

  async getDiagnostics(): Promise<{ incidents: IncidentItem[]; latencies?: Record<string, import("./types").LatencyDistribution> }> {
    if (IS_TAURI) {
      return await sidecarCall<{ incidents: IncidentItem[]; latencies: Record<string, import("./types").LatencyDistribution> }>("get_diagnostics", { limit: 50 });
    }
    return {
      incidents: [...FIXTURE_INCIDENTS],
      latencies: {
        coinbase: { count: 120, p50: 85.0, p95: 142.0, p99: 210.0 },
        kraken: { count: 150, p50: 62.0, p95: 108.0, p99: 175.0 },
      },
    };
  },

  async getSettings(): Promise<import("./types").SystemSettings> {
    if (IS_TAURI) {
      const res = await sidecarCall<{ settings: import("./types").SystemSettings }>("get_settings");
      return res.settings;
    }
    const saved = localStorage.getItem("system_settings");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return {
      retention_days: 7,
      raw_quota_gb: 2,
      audio_enabled: true,
      speech_enabled: false,
      quiet_mode: false,
    };
  },

  async updateSettings(settings: Partial<import("./types").SystemSettings>): Promise<import("./types").SystemSettings> {
    if (IS_TAURI) {
      const res = await sidecarCall<{ settings: import("./types").SystemSettings }>("update_settings", { settings });
      return res.settings;
    }
    const current = await this.getSettings();
    const updated = { ...current, ...settings };
    localStorage.setItem("system_settings", JSON.stringify(updated));
    return updated;
  },

  async exportReplayBundle(options: { mode: "complete" | "sanitized"; eventId?: string }): Promise<any> {
    if (IS_TAURI) {
      return await sidecarCall<any>("export_replay_bundle", options);
    }
    const opp = FIXTURE_OPPORTUNITIES[0];
    return {
      manifest: {
        schema_version: "1.0.0",
        bundle_mode: options.mode,
        event_id: opp.event_id,
        timestamp_utc_ms: opp.timestamp_utc_ms,
        input_hash: opp.input_hash,
      },
      opportunity: opp,
      omissions: options.mode === "complete" ? [] : ["private_balances"],
    };
  },

  async compareCosts(
    side: "buy" | "sell",
    amount: string,
    symbol: string,
    splitRatio: number = 50
  ): Promise<import("./types").CostComparisonResponse> {
    if (IS_TAURI) {
      // In native mode: call sidecar. If it fails, throw visibly (F03).
      return await sidecarCall<import("./types").CostComparisonResponse>("compare_costs", {
        side,
        amount,
        symbol,
        split_ratio: splitRatio,
      });
    }

    // Fixture fallback ONLY when !IS_TAURI (in web browser / demo mode)
    const amt = parseFloat(amount) || 1000;
    const px = side === "buy" ? 85700 : 85690;
    const results: CostComparisonResult[] = [
      {
        venue: "kraken",
        side,
        amount,
        units: side === "buy" ? "USDT" : "BTC",
        is_complete: true,
        acquired_base: (amt / px).toFixed(8),
        quote_spent: (amt * 0.9975).toFixed(2),
        quote_received: (amt * px * 0.9975).toFixed(2),
        fee_quote: (amt * 0.0025).toFixed(2),
        fee_base: "0.00",
        avg_price: String(px),
        total_cost: amount,
        net_proceeds: (amt * px * 0.9975).toFixed(2),
      },
      {
        venue: "coinbase",
        side,
        amount,
        units: side === "buy" ? "USDT" : "BTC",
        is_complete: true,
        acquired_base: (amt / (px + 20)).toFixed(8),
        quote_spent: (amt * 0.9975).toFixed(2),
        quote_received: (amt * (px + 20) * 0.9975).toFixed(2),
        fee_quote: (amt * 0.0025).toFixed(2),
        fee_base: "0.00",
        avg_price: String(px + 20),
        total_cost: amount,
        net_proceeds: (amt * (px + 20) * 0.9975).toFixed(2),
      },
    ];

    const grid: Record<string, CostComparisonResult[]> = {};
    for (const gAmt of ["100.00", "1000.00", "10000.00"]) {
      const gVal = parseFloat(gAmt);
      grid[gAmt] = [
        {
          venue: "kraken",
          side,
          amount: gAmt,
          units: side === "buy" ? "USDT" : "BTC",
          is_complete: true,
          acquired_base: (gVal / px).toFixed(8),
          quote_spent: (gVal * 0.9975).toFixed(2),
          quote_received: (gVal * px * 0.9975).toFixed(2),
          fee_quote: (gVal * 0.0025).toFixed(2),
          fee_base: "0.00",
          avg_price: String(px),
          total_cost: gAmt,
          net_proceeds: (gVal * px * 0.9975).toFixed(2),
        },
        {
          venue: "coinbase",
          side,
          amount: gAmt,
          units: side === "buy" ? "USDT" : "BTC",
          is_complete: true,
          acquired_base: (gVal / (px + 20)).toFixed(8),
          quote_spent: (gVal * 0.9975).toFixed(2),
          quote_received: (gVal * (px + 20) * 0.9975).toFixed(2),
          fee_quote: (gVal * 0.0025).toFixed(2),
          fee_base: "0.00",
          avg_price: String(px + 20),
          total_cost: gAmt,
          net_proceeds: (gVal * (px + 20) * 0.9975).toFixed(2),
        },
      ];
    }

    const cbAlloc = (amt * (splitRatio / 100)).toFixed(2);
    const krAlloc = (amt * ((100 - splitRatio) / 100)).toFixed(2);
    const split: import("./types").SplitOrderResult = {
      side,
      symbol,
      all_complete: true,
      total_base: (amt / (px + 10)).toFixed(8),
      total_spent_or_received: amt.toFixed(2),
      total_fees_quote: (amt * 0.0025).toFixed(2),
      total_fees_base: "0.00",
      effective_avg_price: (px + 10).toFixed(2),
      children: [
        {
          venue: "coinbase",
          allocated_amount: cbAlloc,
          acquired_base: ((amt * (splitRatio / 100)) / (px + 20)).toFixed(8),
          quote_spent: cbAlloc,
          fee_quote: (parseFloat(cbAlloc) * 0.0025).toFixed(2),
          is_complete: true,
        },
        {
          venue: "kraken",
          allocated_amount: krAlloc,
          acquired_base: ((amt * ((100 - splitRatio) / 100)) / px).toFixed(8),
          quote_spent: krAlloc,
          fee_quote: (parseFloat(krAlloc) * 0.0025).toFixed(2),
          is_complete: true,
        },
      ],
    };

    return { results, grid, split };
  },

  async replayEvent(eventId: string, overrideFee?: string): Promise<any> {
    if (IS_TAURI) {
      return await sidecarCall<any>("replay_event", { event_id: eventId, override_fee: overrideFee ?? null });
    }
    const opp = FIXTURE_OPPORTUNITIES.find((o) => o.event_id === eventId);
    if (!opp) throw new Error("Event not found");
    const feeMod = overrideFee ? parseFloat(overrideFee) : 0.0025;
    const replayedProfit = (parseFloat(opp.net_profit_quote) * (0.0025 / feeMod)).toFixed(2);
    return {
      status: "REPLAYED",
      is_exact_match: !overrideFee,
      event_id: eventId,
      original_profit: opp.net_profit_quote,
      replayed_profit: replayedProfit,
      input_hash: opp.input_hash,
      config_hash: opp.config_hash,
    };
  },

  async exportIncidentBundle(incidentId: string): Promise<any> {
    if (IS_TAURI) {
      return await sidecarCall<any>("export_incident_bundle", { incident_id: incidentId });
    }
    const inc = FIXTURE_INCIDENTS.find((i) => i.incident_id === incidentId);
    if (!inc) throw new Error("Incident not found");
    return {
      incident_id: inc.incident_id,
      fault_class: inc.fault_class,
      trigger: inc.trigger,
      severity: inc.severity,
      evidence: inc.raw_evidence,
      offline_reproduction_command: `ohmycrypto diagnostics reproduce --bundle ${incidentId}.json`,
    };
  },
};
