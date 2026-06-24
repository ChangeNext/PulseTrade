import type { HealthStatus } from "../types/strategy";

function StatusItem({ label, connected, standby = false }: { label: string; connected: boolean; standby?: boolean }) {
  const tone = connected ? "online" : standby ? "standby" : "offline";
  const text = connected ? "연결됨" : standby ? "미설정" : "끊김";
  return <div className="connection-item"><span className={`status-dot ${tone}`} /><span><small>{label}</small><strong>{text}</strong></span></div>;
}

export function ConnectionStatus({ health }: { health: HealthStatus | null }) {
  const telegramConfigured = Boolean(health?.telegram_configured);
  const telegramConnected = Boolean(health?.telegram_connected ?? telegramConfigured);
  return (
    <div className="header-status" aria-label="시스템 연결 상태">
      <StatusItem label="KIS REST" connected={Boolean(health?.kis_account_connected)} standby={!health?.kis_configured} />
      <StatusItem label="WebSocket" connected={Boolean(health?.websocket_connected)} />
      <StatusItem label="Telegram" connected={telegramConnected} standby={!telegramConfigured} />
    </div>
  );
}
