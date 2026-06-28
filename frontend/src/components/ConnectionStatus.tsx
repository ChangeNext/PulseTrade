import type { HealthStatus } from "../types/strategy";

type ConnectionState = "CONNECTED" | "CONNECTING" | "NOT_CONFIGURED" | "DISCONNECTED";

function StatusItem({ label, state, standby = false }: { label: string; state: ConnectionState | "online" | "standby" | "offline"; standby?: boolean }) {
  const normalized = state === "online" ? "CONNECTED" : state === "standby" ? "NOT_CONFIGURED" : state === "offline" ? "DISCONNECTED" : state;
  const tone = normalized === "CONNECTED" ? "online" : normalized === "CONNECTING" ? "standby" : normalized === "NOT_CONFIGURED" ? "standby" : "offline";
  const text = normalized === "CONNECTED" ? "연결됨" : normalized === "CONNECTING" ? "연결 중" : normalized === "NOT_CONFIGURED" || standby ? "미설정" : "끊김";
  return <div className="connection-item"><span className={`status-dot ${tone}`} /><span><small>{label}</small><strong>{text}</strong></span></div>;
}

export function ConnectionStatus({ health }: { health: HealthStatus | null }) {
  const telegramConfigured = Boolean(health?.telegram_configured);
  const telegramConnected = Boolean(health?.telegram_connected ?? telegramConfigured);
  const websocketState = health?.websocket_state ?? (health?.websocket_connected ? "CONNECTED" : "DISCONNECTED");
  return (
    <div className="header-status" aria-label="시스템 연결 상태">
      <StatusItem label="KIS REST" state={health?.rest_connected ? "CONNECTED" : health?.kis_configured ? "DISCONNECTED" : "NOT_CONFIGURED"} />
      <StatusItem label="WebSocket" state={websocketState} />
      <StatusItem label="Telegram" state={telegramConnected ? "CONNECTED" : telegramConfigured ? "DISCONNECTED" : "NOT_CONFIGURED"} />
    </div>
  );
}
