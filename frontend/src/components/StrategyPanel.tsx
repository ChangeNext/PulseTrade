import type { StrategyStatusData } from "../types/strategy";

function Toggle({ label, description, checked, disabled = false, onChange }: { label: string; description: string; checked: boolean; disabled?: boolean; onChange: (value: boolean) => void }) {
  return <div className="strategy-option"><div><strong>{label}</strong><span>{description}</span></div><label className="toggle"><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><span aria-hidden="true" /></label></div>;
}

export function StrategyPanel({ strategy, emergencyStopped, onAutoOrderToggle }: { strategy: StrategyStatusData | null; emergencyStopped: boolean; onAutoOrderToggle: (enabled: boolean) => void }) {
  const desired = Boolean(strategy?.desired_enabled);
  const effective = Boolean(strategy?.auto_order_enabled);
  const ready = Boolean(strategy?.ready);
  const reason = strategy?.readiness_reason;

  return (
    <section className="panel strategy-panel">
      <div className="panel-heading"><div><p className="section-label">STRATEGY ENGINE</p><h2>전략 제어</h2></div><span className={`engine-state ${effective ? "running" : "idle"}`}>{strategy?.status ?? "OFFLINE"}</span></div>
      <div className="strategy-list">
        <Toggle label="ORB 전략" description="09:00–09:05 범위 돌파" checked disabled onChange={() => undefined} />
        <Toggle label="VWAP 필터" description="당일 거래량 가중 평균가 상회" checked disabled onChange={() => undefined} />
        <Toggle label="거래량 급증 필터" description="직전 20분 평균 대비 2배" checked disabled onChange={() => undefined} />
        <div className="strategy-separator" />
        <Toggle label="자동주문 희망 상태" description={emergencyStopped ? "긴급 정지로 차단됨" : ready ? "준비 완료" : reason ?? "브로커 및 전략 데이터 대기 중"} checked={desired} disabled={emergencyStopped} onChange={onAutoOrderToggle} />
      </div>
      <div className="strategy-safety safe"><span>감시 종목: {(strategy?.watched_symbols ?? []).join(", ") || "미설정"}</span></div>
      {(strategy?.signals ?? []).map((signal) => <div className={`strategy-safety ${signal.action === "BUY" ? "armed" : "safe"}`} key={signal.symbol}><span className="status-dot" /><strong>{signal.symbol}</strong> {signal.action} · {Number(signal.score).toFixed(1)}점</div>)}
      <div className={`strategy-safety ${effective ? "armed" : "safe"}`}><span className="status-dot" />{effective ? "PAPER 자동 주문이 실행 중입니다." : desired ? "자동 주문 활성 조건을 기다리고 있습니다." : "자동 주문이 비활성화되어 있습니다."}</div>
    </section>
  );
}
