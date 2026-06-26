import type { StrategyStatusData } from "../types/strategy";

function Toggle({
  label,
  description,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="strategy-option">
      <div>
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
        <span aria-hidden="true" />
      </label>
    </div>
  );
}

function statusText(strategy: StrategyStatusData | null, emergencyStopped: boolean) {
  if (!strategy) return "OFFLINE";
  if (emergencyStopped) return "STOPPED";
  if (strategy.signal_only) return "SIGNAL ONLY";
  return strategy.status;
}

export function StrategyPanel({
  strategy,
  emergencyStopped,
  onAutoOrderToggle,
}: {
  strategy: StrategyStatusData | null;
  emergencyStopped: boolean;
  onAutoOrderToggle: (enabled: boolean) => void;
}) {
  const desired = Boolean(strategy?.desired_enabled);
  const effective = Boolean(strategy?.auto_order_enabled);
  const ready = Boolean(strategy?.ready);
  const reason = strategy?.readiness_reason;
  const signal = strategy?.signals?.[0];
  const hasSignal = Boolean(signal);
  const watchedSymbols = (strategy?.watched_symbols ?? []).join(", ") || "미설정";
  const signalState = signal ? `${signal.action} · ${Number(signal.score).toFixed(1)}점` : "대기";
  const autoDescription = emergencyStopped
    ? "긴급정지로 자동주문이 차단됨"
    : strategy?.signal_only
      ? "현재 신호 전용 모드라 실전 자동주문은 차단됨"
      : ready
        ? "브로커와 실시간 데이터 준비 완료"
        : reason ?? "브로커 및 전략 데이터 대기 중";

  return (
    <section className="panel strategy-panel">
      <div className="panel-heading">
        <div>
          <p className="section-label">STRATEGY ENGINE</p>
          <h2>전략 제어</h2>
        </div>
        <span className={`engine-state ${effective ? "running" : "idle"}`}>{statusText(strategy, emergencyStopped)}</span>
      </div>

      <div className="strategy-status-grid">
        <article>
          <span>점수 신호</span>
          <strong className={hasSignal && Number(signal?.score) < 0 ? "negative" : hasSignal ? "positive" : "neutral"}>{signalState}</strong>
          <em>{hasSignal ? signal?.reason : "차트 데이터 수집 중"}</em>
        </article>
        <article>
          <span>실시간 준비</span>
          <strong className={ready ? "positive" : "neutral"}>{ready ? "READY" : "WAIT"}</strong>
          <em>{reason ?? "REST 가격/차트 기반 점수 산출 가능"}</em>
        </article>
        <article>
          <span>자동 주문</span>
          <strong className={effective ? "negative" : "neutral"}>{effective ? "ACTIVE" : desired ? "ARMED" : "OFF"}</strong>
          <em>{autoDescription}</em>
        </article>
      </div>

      <div className="strategy-list strategy-list-single">
        <Toggle label="자동주문 허용" description={autoDescription} checked={desired} disabled={emergencyStopped || Boolean(strategy?.signal_only)} onChange={onAutoOrderToggle} />
      </div>

      <div className="strategy-safety safe">
        <span>감시 종목: {watchedSymbols}</span>
      </div>
      {(strategy?.signals ?? []).map((item) => (
        <div className={`strategy-safety ${item.action === "BUY" ? "armed" : "safe"}`} key={item.symbol}>
          <span className="status-dot" />
          <strong>{item.symbol}</strong> {item.action} · {Number(item.score).toFixed(1)}점
        </div>
      ))}
      <div className={`strategy-safety ${effective ? "armed" : "safe"}`}>
        <span className="status-dot" />
        {effective ? "자동 주문이 실행 중입니다." : desired ? "자동 주문 조건을 기다리고 있습니다." : "자동 주문은 비활성화되어 있습니다."}
      </div>
    </section>
  );
}
