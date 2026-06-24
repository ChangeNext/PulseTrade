export interface StrategyStatusData {
  name: string;
  enabled: boolean;
  signal_only: boolean;
  status: string;
  orb_enabled?: boolean;
  vwap_enabled?: boolean;
  volume_surge_enabled?: boolean;
  auto_order_enabled?: boolean;
}

export interface HealthStatus {
  status: string;
  mode: "SIM" | "PAPER" | "LIVE";
  live_enabled: boolean;
  kis_configured: boolean;
  kis_account_connected?: boolean;
  api_connected: boolean;
  websocket_connected: boolean;
  telegram_configured?: boolean;
  telegram_connected?: boolean;
  emergency_stopped: boolean;
}

export type SystemLogLevel = "INFO" | "WARN" | "ERROR" | "BLOCK";

export interface SystemLogEntry {
  id: string;
  timestamp: string;
  category: "API" | "ORDER" | "RISK" | "WEBSOCKET" | "TELEGRAM" | "SYSTEM";
  level: SystemLogLevel;
  message: string;
}
