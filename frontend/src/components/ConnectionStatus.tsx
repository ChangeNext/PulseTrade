import type { HealthStatus } from "../types/strategy";

type ConnectionState = "CONNECTED" | "CONNECTING" | "NOT_CONFIGURED" | "DISCONNECTED" | "UNKNOWN";

function StatusItem({ label, state }: { label: string; state: ConnectionState }) {
  const tone =
    state === "CONNECTED"
      ? "online"
      : state === "DISCONNECTED"
        ? "offline"
        : "standby";
  const text =
    state === "CONNECTED"
      ? "연결됨"
      : state === "CONNECTING"
        ? "연결 중"
        : state === "NOT_CONFIGURED"
          ? "미설정"
          : state === "UNKNOWN"
            ? "확인중"
            : "연결 실패";

  return (
    <div className="connection-item">
      <span className={`status-dot ${tone}`} />
      <span>
        <small>{label}</small>
        <strong>{text}</strong>
      </span>
    </div>
  );
}

export function ConnectionStatus({ health }: { health: HealthStatus | null }) {
  const telegramConfigured = Boolean(health?.telegram_configured);
  const telegramConnected = Boolean(health?.telegram_connected ?? telegramConfigured);
  const websocketState = health?.websocket_state ?? (health?.websocket_connected ? "CONNECTED" : "DISCONNECTED");

  return (
    <div className="header-status" aria-label="시스템 연결 상태">
      <StatusItem
        label="KIS REST"
        state={!health ? "UNKNOWN" : health.rest_connected ? "CONNECTED" : health.kis_configured ? "DISCONNECTED" : "NOT_CONFIGURED"}
      />
      <StatusItem label="WebSocket" state={!health ? "UNKNOWN" : websocketState} />
      <StatusItem
        label="Telegram"
        state={!health ? "UNKNOWN" : telegramConnected ? "CONNECTED" : telegramConfigured ? "DISCONNECTED" : "NOT_CONFIGURED"}
      />
    </div>
  );
}
