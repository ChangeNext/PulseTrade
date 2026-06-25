import { type FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import type { ManualOrderInput } from "../types/order";

interface ManualOrderPanelProps {
  mode: "SIM" | "PAPER" | "LIVE";
  liveEnabled: boolean;
  emergencyStopped: boolean;
  onSubmitted: () => void;
  onSystemMessage: (message: string, error?: boolean) => void;
}

interface ConfirmModalProps {
  order: ManualOrderInput;
  mode: "SIM" | "PAPER" | "LIVE";
  busy: boolean;
  onCancel: () => void;
  onConfirm: (liveChecked: boolean) => void;
}

function ConfirmModal({ order, mode, busy, onCancel, onConfirm }: ConfirmModalProps) {
  const [liveChecked, setLiveChecked] = useState(false);
  const isLive = mode === "LIVE";

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape" && !busy) onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, onCancel]);

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <section className={`confirm-modal ${isLive ? "live-modal" : ""}`} role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <div className="modal-icon">{isLive ? "!" : "?"}</div>
        <p className="section-label">ORDER CONFIRMATION</p>
        <h2 id="confirm-title">{isLive ? "실전 주문을 전송할까요?" : "주문 내용을 확인하세요"}</h2>
        {isLive && <div className="live-warning"><strong>LIVE 실거래</strong><span>이 주문은 실제 계좌와 자금에 반영됩니다.</span></div>}
        <dl className="order-review">
          <div><dt>종목코드</dt><dd>{order.symbol}</dd></div><div><dt>주문구분</dt><dd className={order.side === "BUY" ? "positive" : "negative"}>{order.side === "BUY" ? "매수" : "매도"}</dd></div><div><dt>주문가격</dt><dd>{order.price.toLocaleString("ko-KR")}원</dd></div><div><dt>수량</dt><dd>{order.quantity.toLocaleString("ko-KR")}주</dd></div><div className="order-total"><dt>예상 주문금액</dt><dd>{(order.price * order.quantity).toLocaleString("ko-KR")}원</dd></div>
        </dl>
        {isLive && <label className="live-confirm-check"><input type="checkbox" checked={liveChecked} onChange={(event) => setLiveChecked(event.target.checked)} /><span>실제 계좌에 주문이 전송됨을 확인했습니다.</span></label>}
        <div className="modal-actions"><button type="button" className="button ghost" onClick={onCancel} disabled={busy}>취소</button><button type="button" className={`button ${order.side === "BUY" ? "buy-button" : "sell-button"}`} onClick={() => onConfirm(liveChecked)} disabled={busy || (isLive && !liveChecked)}>{busy ? "전송 중..." : `${order.side === "BUY" ? "매수" : "매도"} 주문 전송`}</button></div>
      </section>
    </div>,
    document.body,
  );
}

export function ManualOrderPanel({ mode, liveEnabled, emergencyStopped, onSubmitted, onSystemMessage }: ManualOrderPanelProps) {
  const [symbol, setSymbol] = useState("005930");
  const [quantity, setQuantity] = useState(1);
  const [price, setPrice] = useState(0);
  const [armed, setArmed] = useState(false);
  const [pendingSide, setPendingSide] = useState<"BUY" | "SELL" | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const valid = /^\d{6}$/.test(symbol) && quantity > 0 && price > 0;
  const liveLocked = mode === "LIVE" && !liveEnabled;
  const disabled = !armed || !valid || emergencyStopped || busy || liveLocked;

  function requestConfirmation(event: FormEvent, side: "BUY" | "SELL") {
    event.preventDefault();
    if (!disabled) setPendingSide(side);
  }

  async function sendOrder(liveChecked: boolean) {
    if (!pendingSide) return;
    setBusy(true);
    const order: ManualOrderInput = { symbol, side: pendingSide, quantity, price };
    if (mode === "LIVE" && liveChecked) order.live_confirmation = "I_UNDERSTAND_LIVE_TRADING_RISK";
    try {
      const result = await api.submitOrder(order);
      const text = `${result.state}: ${result.message}`;
      setMessage(text); onSystemMessage(text, result.state === "REJECTED" || result.state === "ERROR");
      setPendingSide(null); setArmed(false); onSubmitted();
    } catch (error) {
      const text = error instanceof Error ? error.message : "주문 요청에 실패했습니다.";
      setMessage(text); onSystemMessage(text, true);
    } finally { setBusy(false); }
  }

  return (
    <section className={`panel manual-order-panel ${mode === "LIVE" ? "live-order-panel" : ""}`}>
      <div className="panel-heading"><div><p className="section-label">MANUAL ORDER</p><h2>수동 주문</h2></div><span className={`mode-chip mode-${mode.toLowerCase()}`}>{mode}</span></div>
      {liveLocked && <div className="inline-live-warning"><strong>LIVE LOCKED</strong> 실계좌 주문 전송은 비활성화되어 있습니다.</div>}
      {mode === "LIVE" && liveEnabled && <div className="inline-live-warning"><strong>LIVE ENABLED</strong> 실계좌 주문 전송 전 확인창이 표시됩니다.</div>}
      <form className="manual-order-form">
        <label><span>종목코드</span><input value={symbol} onChange={(event) => setSymbol(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" placeholder="6자리 코드" /></label>
        <div className="split-fields"><label><span>주문 가격</span><div className="input-suffix"><input type="number" min="1" value={price || ""} onChange={(event) => setPrice(Number(event.target.value))} placeholder="0" /><em>원</em></div></label><label><span>수량</span><div className="input-suffix"><input type="number" min="1" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} /><em>주</em></div></label></div>
        <div className="order-estimate"><span>예상 주문금액</span><strong>{(price * quantity).toLocaleString("ko-KR")}원</strong></div>
        <label className="arm-control"><input type="checkbox" checked={armed} onChange={(event) => setArmed(event.target.checked)} disabled={emergencyStopped} /><span>수동 주문 기능 활성화</span></label>
        <div className="order-actions"><button type="submit" className="button buy-button" disabled={disabled} onClick={(event) => requestConfirmation(event, "BUY")}>매수</button><button type="submit" className="button sell-button" disabled={disabled} onClick={(event) => requestConfirmation(event, "SELL")}>매도</button></div>
        {emergencyStopped && <p className="blocked-message">긴급 STOP 상태에서는 주문할 수 없습니다.</p>}
        {liveLocked && <p className="blocked-message">LIVE 주문 라우팅은 현재 설정에서 잠겨 있습니다.</p>}
        {message && <p className="form-message">{message}</p>}
      </form>
      {pendingSide && <ConfirmModal order={{ symbol, side: pendingSide, quantity, price }} mode={mode} busy={busy} onCancel={() => setPendingSide(null)} onConfirm={sendOrder} />}
    </section>
  );
}
