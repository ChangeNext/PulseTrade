import { useState } from "react";
import type { StrategyStatusData } from "../types/strategy";

function Toggle({ label, description, checked, disabled = false, onChange }: { label: string; description: string; checked: boolean; disabled?: boolean; onChange: (value: boolean) => void }) {
  return <div className="strategy-option"><div><strong>{label}</strong><span>{description}</span></div><label className="toggle"><input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><span aria-hidden="true" /></label></div>;
}

export function StrategyPanel({ strategy, emergencyStopped, onAutoOrderToggle }: { strategy: StrategyStatusData | null; emergencyStopped: boolean; onAutoOrderToggle: (enabled: boolean) => void }) {
  const [orb, setOrb] = useState(strategy?.orb_enabled ?? true);
  const [vwap, setVwap] = useState(strategy?.vwap_enabled ?? true);
  const [volume, setVolume] = useState(strategy?.volume_surge_enabled ?? true);
  const [signalOnly, setSignalOnly] = useState(strategy?.signal_only ?? true);
  const autoOrder = strategy?.auto_order_enabled ?? strategy?.enabled ?? false;

  function changeSignalOnly(enabled: boolean) {
    setSignalOnly(enabled);
    if (enabled && autoOrder) onAutoOrderToggle(false);
  }

  return (
    <section className="panel strategy-panel">
      <div className="panel-heading"><div><p className="section-label">STRATEGY ENGINE</p><h2>전략 제어</h2></div><span className={`engine-state ${strategy?.status === "RUNNING" ? "running" : "idle"}`}>{strategy?.status ?? "OFFLINE"}</span></div>
      <div className="strategy-list">
        <Toggle label="ORB 전략" description="장 초반 가격 범위 돌파" checked={orb} onChange={setOrb} />
        <Toggle label="VWAP 필터" description="거래량 가중 평균가 확인" checked={vwap} onChange={setVwap} />
        <Toggle label="거래량 급증 필터" description="평균 대비 거래량 증가 확인" checked={volume} onChange={setVolume} />
        <div className="strategy-separator" />
        <Toggle label="Signal Only" description="신호만 생성하고 주문하지 않음" checked={signalOnly} onChange={changeSignalOnly} />
        <Toggle label="자동주문" description={emergencyStopped ? "긴급 정지로 차단됨" : "RiskManager 승인 후 주문"} checked={autoOrder} disabled={signalOnly || emergencyStopped} onChange={onAutoOrderToggle} />
      </div>
      <div className={`strategy-safety ${signalOnly ? "safe" : "armed"}`}><span className="status-dot" />{signalOnly ? "현재 신호 전용 모드입니다." : "자동 주문 실행이 허용된 상태입니다."}</div>
    </section>
  );
}

