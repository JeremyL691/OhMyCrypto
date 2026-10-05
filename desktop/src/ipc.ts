import { CostComparisonResult, EngineStatus, IncidentItem, OpportunityItem } from "./types";

const IS_TAURI = typeof window !== "undefined" && Boolean((window as any).__TAURI_INTERNALS__);

// Realistic fixture dataset explicitly labeled as demo/fixture
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

let currentStatus: EngineStatus = {
  status: "idle",
  uptime_sec: 142,
  pid: 63769,
  active_symbol: "BTC/USDT",
  active_budget: "1000.00",
  is_demo: !IS_TAURI,
};

export const api = {
  async getStatus(): Promise<EngineStatus> {
    return { ...currentStatus };
  },

  async startMonitor(symbol: string, budget: string): Promise<EngineStatus> {
    currentStatus = {
      ...currentStatus,
      status: "monitoring",
      active_symbol: symbol,
      active_budget: budget,
    };
    return currentStatus;
  },

  async pauseMonitor(): Promise<EngineStatus> {
    currentStatus = { ...currentStatus, status: "paused" };
    return currentStatus;
  },

  async resumeMonitor(): Promise<EngineStatus> {
    currentStatus = { ...currentStatus, status: "monitoring" };
    return currentStatus;
  },

  async stopMonitor(): Promise<EngineStatus> {
    currentStatus = { ...currentStatus, status: "stopped" };
    return currentStatus;
  },

  async getOpportunities(): Promise<OpportunityItem[]> {
    return [...FIXTURE_OPPORTUNITIES];
  },

  async getIncidents(): Promise<IncidentItem[]> {
    return [...FIXTURE_INCIDENTS];
  },

  async compareCosts(side: "buy" | "sell", amount: string, _symbol: string): Promise<CostComparisonResult[]> {
    const amt = parseFloat(amount) || 1000;
    if (side === "buy") {
      return [
        {
          venue: "kraken",
          side: "buy",
          amount: amount,
          units: "USDT",
          is_complete: true,
          acquired_base: (amt / 85695.6).toFixed(8),
          quote_spent: (amt * 0.9975).toFixed(2),
          fee_quote: (amt * 0.0025).toFixed(2),
          fee_base: "0.00",
          avg_price: "85695.60",
          total_cost: amount,
        },
        {
          venue: "coinbase",
          side: "buy",
          amount: amount,
          units: "USDT",
          is_complete: true,
          acquired_base: (amt / 85718.8).toFixed(8),
          quote_spent: (amt * 0.9975).toFixed(2),
          fee_quote: (amt * 0.0025).toFixed(2),
          fee_base: "0.00",
          avg_price: "85718.80",
          total_cost: amount,
        },
      ];
    } else {
      return [
        {
          venue: "kraken",
          side: "sell",
          amount: amount,
          units: "BTC",
          is_complete: true,
          quote_received: (amt * 85695.5 * 0.9975).toFixed(2),
          fee_quote: (amt * 85695.5 * 0.0025).toFixed(2),
          fee_base: "0.00",
          avg_price: "85695.50",
          net_proceeds: (amt * 85695.5 * 0.9975).toFixed(2),
        },
        {
          venue: "coinbase",
          side: "sell",
          amount: amount,
          units: "BTC",
          is_complete: true,
          quote_received: (amt * 85690.2 * 0.9975).toFixed(2),
          fee_quote: (amt * 85690.2 * 0.0025).toFixed(2),
          fee_base: "0.00",
          avg_price: "85690.20",
          net_proceeds: (amt * 85690.2 * 0.9975).toFixed(2),
        },
      ];
    }
  },

  async replayEvent(eventId: string, overrideFee?: string): Promise<any> {
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
