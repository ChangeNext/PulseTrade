import type { SystemLogEntry } from "../types/strategy";

export function SystemLog({ logs }: { logs: SystemLogEntry[] }) {
  return (
    <section className="panel system-log-panel">
      <div className="panel-heading"><div><p className="section-label">SYSTEM LOG</p><h2>시스템 이벤트</h2></div><span className="live-indicator"><i /> LIVE</span></div>
      <div className="system-log-list" role="log" aria-live="polite">
        {logs.length ? logs.slice(0, 12).map((log) => <article className={`log-row level-${log.level.toLowerCase()}`} key={log.id}>
          <time>{new Date(log.timestamp).toLocaleTimeString("ko-KR", { hour12: false })}</time><span className="log-category">{log.category}</span><span className="log-level">{log.level}</span><p>{log.message}</p>
        </article>) : <div className="empty-log"><span>✓</span><p>표시할 시스템 이벤트가 없습니다.</p></div>}
      </div>
    </section>
  );
}

