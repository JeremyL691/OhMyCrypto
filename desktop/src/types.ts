export type TabKey = "overview" | "opportunities" | "diagnostics" | "cost" | "settings";

export interface FeeProfile {
  venue: string;
  maker_rate: string;
  taker_rate: string;
  fixed_fee: string;
  fee_currency: string;
  charged_on: "quote" | "base";
  is_override: boolean;
}

export interface FillDetail {
  side: "buy" | "sell";
  requested_amount: string;
  acquired_base: string;
  quote_spent: string;
  quote_received: string;
  avg_price: string;
  fee_quote: string;
  fee_base: string;
  residual_quote: string;
  residual_base: string;
  levels_consumed: number;
  is_complete: boolean;
  rejection_reason?: string;
  spent_quote?: string;
  proceeds_quote?: string;
  fee_paid?: string;
  effective_avg_price?: string;
}

export interface OpportunityItem {
  event_id: string;
  episode_id: string;
  route_key: string;
  timestamp_utc_ms: number;
  symbol: string;
  buy_venue: string;
  sell_venue: string;
  budget_amount: string;
  budget_units: string;
  net_profit_quote: string;
  effective_spread: string;
  midpoint_price: string;
  is_positive: boolean;
  is_eligible: boolean;
  eligibility_reasons: string[];
  input_hash: string;
  config_hash: string;
  follow_up_500ms?: "persisted" | "failed" | "unknown";
  follow_up_1s?: "persisted" | "failed" | "unknown";
  follow_up_3s?: "persisted" | "failed" | "unknown";
  continuous_persistence_status?: "continuous" | "interrupted" | "unknown";
  notification_state: string;
  buy_fill: FillDetail;
  sell_fill: FillDetail;
}

export interface IncidentItem {
  incident_id: string;
  connector: string;
  channel: string;
  fault_class: string;
  trigger: string;
  severity: "warning" | "error" | "critical";
  opened_at_ms: number;
  closed_at_ms?: number;
  is_recovered: boolean;
  raw_evidence: Record<string, any>;
}

export interface CostComparisonResult {
  venue: string;
  side: "buy" | "sell";
  amount: string;
  units: string;
  is_complete: boolean;
  rejection_reason?: string;
  acquired_base?: string;
  quote_spent?: string;
  quote_received?: string;
  fee_quote: string;
  fee_base: string;
  avg_price: string;
  total_cost?: string;
  net_proceeds?: string;
}

export interface EngineStatus {
  status: "idle" | "monitoring" | "paused" | "stopped";
  uptime_sec: number;
  pid: number;
  active_symbol: string;
  active_budget: string;
  is_demo: boolean;
}

export interface SystemSettings {
  retention_days: number;
  raw_quota_gb: number;
  audio_enabled: boolean;
  speech_enabled: boolean;
  quiet_mode: boolean;
}

export interface LatencyDistribution {
  count: number;
  p50: number;
  p95: number;
  p99: number;
}

export interface SplitOrderChild {
  venue: string;
  allocated_amount: string;
  acquired_base?: string;
  quote_spent?: string;
  quote_received?: string;
  fee_quote: string;
  is_complete: boolean;
  rejection_reason?: string;
}

export interface SplitOrderResult {
  side: "buy" | "sell";
  symbol: string;
  all_complete: boolean;
  total_base: string;
  total_spent_or_received: string;
  total_fees_quote: string;
  total_fees_base: string;
  effective_avg_price: string;
  children: SplitOrderChild[];
}

export interface CostComparisonResponse {
  results: CostComparisonResult[];
  grid?: Record<string, CostComparisonResult[]>;
  split?: SplitOrderResult | null;
}
