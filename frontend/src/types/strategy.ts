export interface StrategyStatusData {
  name: string;
  enabled: boolean;
  signal_only: boolean;
  status: string;
  orb_enabled?: boolean;
  vwap_enabled?: boolean;
  volume_surge_enabled?: boolean;
  auto_order_enabled?: boolean;
  desired_enabled?: boolean;
  ready?: boolean;
  readiness_reason?: string | null;
  watched_symbols?: string[];
  signals?: Array<{
    symbol: string;
    action: "BUY" | "WAIT" | "SELL" | "EXIT";
    score: number;
    reason: string;
    components: Array<{ name: string; score: number; ready: boolean; reason: string }>;
  }>;
}

export interface HealthStatus {
  status: string;
  mode: "SIM" | "PAPER" | "LIVE";
  live_enabled: boolean;
  kis_configured: boolean;
  kis_account_connected?: boolean;
  rest_connected?: boolean;
  api_connected: boolean;
  websocket_connected: boolean;
  telegram_configured?: boolean;
  telegram_connected?: boolean;
  emergency_stopped: boolean;
  account_synced?: boolean;
  orders_synced?: boolean;
  pnl_synced?: boolean;
  strategy_ready?: boolean;
  strategy_error?: string | null;
  automation_desired?: boolean;
  automation_effective?: boolean;
}

export type SystemLogLevel = "INFO" | "WARN" | "ERROR" | "BLOCK";

export interface SystemLogEntry {
  id: string;
  timestamp: string;
  category: "API" | "ORDER" | "RISK" | "WEBSOCKET" | "TELEGRAM" | "SYSTEM";
  level: SystemLogLevel;
  message: string;
}
