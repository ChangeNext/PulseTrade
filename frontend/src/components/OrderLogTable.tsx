import type { Order, OrderState } from "../types/order";

const stateTone = (state: OrderState) => {
  if (["FILLED", "ORDER_SENT"].includes(state)) return "success";
  if (["REJECTED", "ERROR"].includes(state)) return "danger";
  if (["CANCELED", "CANCEL_REQUESTED"].includes(state)) return "muted";
  return "waiting";
};

export function OrderLogTable({ orders, onCancel }: { orders: Order[]; onCancel: (orderId: string) => void }) {
  return (
    <section className="panel table-panel order-log-panel">
      <div className="panel-heading"><div><p className="section-label">ORDER LOG</p><h2>주문 로그</h2></div><span className="count-badge">최근 {orders.length}건</span></div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>시간</th><th>종목</th><th>구분</th><th className="numeric">가격</th><th className="numeric">주문/체결</th><th>상태</th><th>출처</th><th>동작</th><th>메시지</th></tr></thead>
          <tbody>{orders.length ? orders.map((order) => {
            const cancelable = ["ORDER_SENT", "PARTIALLY_FILLED", "RECONCILING"].includes(order.state);
            return <tr key={order.id}>
              <td className="time-cell">{new Date(order.created_at).toLocaleTimeString("ko-KR", { hour12: false })}</td><td className="symbol-cell">{order.symbol}</td><td><span className={`side side-${order.side.toLowerCase()}`}>{order.side === "BUY" ? "매수" : "매도"}</span></td><td className="numeric">{Number(order.price).toLocaleString("ko-KR")}</td><td className="numeric">{order.quantity.toLocaleString("ko-KR")} / {Number(order.filled_quantity ?? 0).toLocaleString("ko-KR")}</td><td><span className={`state-badge ${stateTone(order.state)}`}>{order.state}</span></td><td>{order.source ?? "MANUAL"}{order.reprice_count > 0 ? ` R${order.reprice_count}` : ""}</td><td>{cancelable && <button type="button" className="button ghost" onClick={() => onCancel(order.id)}>취소</button>}</td><td className="message-cell">{order.message}{Number(order.commission ?? 0) + Number(order.tax ?? 0) > 0 ? ` · 비용 ${(Number(order.commission ?? 0) + Number(order.tax ?? 0)).toLocaleString("ko-KR")}원` : ""}</td>
            </tr>;
          }) : <tr><td colSpan={9} className="empty-state">주문 기록이 없습니다.</td></tr>}</tbody>
        </table>
      </div>
    </section>
  );
}
