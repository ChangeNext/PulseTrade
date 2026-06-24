import type { Order, OrderState } from "../types/order";

const stateTone = (state: OrderState) => {
  if (["FILLED", "ORDER_SENT"].includes(state)) return "success";
  if (["REJECTED", "ERROR"].includes(state)) return "danger";
  if (["CANCELED", "CANCEL_REQUESTED"].includes(state)) return "muted";
  return "waiting";
};

export function OrderLogTable({ orders }: { orders: Order[] }) {
  return (
    <section className="panel table-panel order-log-panel">
      <div className="panel-heading"><div><p className="section-label">ORDER LOG</p><h2>주문 로그</h2></div><span className="count-badge">최근 {orders.length}건</span></div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>시간</th><th>종목</th><th>주문구분</th><th className="numeric">가격</th><th className="numeric">수량</th><th>상태</th><th>메시지</th></tr></thead>
          <tbody>{orders.length ? orders.map((order) => <tr key={order.id}>
            <td className="time-cell">{new Date(order.created_at).toLocaleTimeString("ko-KR", { hour12: false })}</td><td className="symbol-cell">{order.symbol}</td><td><span className={`side side-${order.side.toLowerCase()}`}>{order.side === "BUY" ? "매수" : "매도"}</span></td><td className="numeric">{Number(order.price).toLocaleString("ko-KR")}</td><td className="numeric">{order.quantity.toLocaleString("ko-KR")}</td><td><span className={`state-badge ${stateTone(order.state)}`}>{order.state}</span></td><td className="message-cell">{order.message}</td>
          </tr>) : <tr><td colSpan={7} className="empty-state">주문 기록이 없습니다.</td></tr>}</tbody>
        </table>
      </div>
    </section>
  );
}

