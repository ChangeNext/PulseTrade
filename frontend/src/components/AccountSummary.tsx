import type { AccountSummaryData, Position } from "../types/account";
import type { Order } from "../types/order";

const won = new Intl.NumberFormat("ko-KR", {
  style: "currency",
  currency: "KRW",
  maximumFractionDigits: 0,
});

interface AccountSummaryProps {
  data: AccountSummaryData | null;
  positions: Position[];
  orders: Order[];
}

export function AccountSummary({ data, positions, orders }: AccountSummaryProps) {
  const calculatedUnrealized = positions.reduce((sum, position) => {
    const pnl = position.evaluation_pnl
      ?? (position.current_price - position.average_price) * position.quantity;
    return sum + pnl;
  }, 0);
  const unrealized = data?.unrealized_pnl ?? calculatedUnrealized;
  const today = new Date().toDateString();
  const todayOrders = orders.filter((order) => new Date(order.created_at).toDateString() === today);
  const orderCount = data?.daily_order_count ?? todayOrders.length;
  const lossLimitReached = data?.daily_loss_limit_reached ?? false;

  const pnlClass = (value: number) => value > 0 ? "positive" : value < 0 ? "negative" : "neutral";

  return (
    <section className="panel account-panel">
      <div className="panel-heading">
        <div><p className="section-label">ACCOUNT</p><h2>계좌 요약</h2></div>
        <span className={`risk-badge ${lossLimitReached ? "danger" : "safe"}`}>
          손실 제한 {lossLimitReached ? "도달" : "정상"}
        </span>
      </div>
      <div className="account-metrics">
        <article><span>예수금</span><strong>{won.format(data?.cash ?? 0)}</strong></article>
        <article><span>총 평가금액</span><strong>{won.format(data?.total_value ?? 0)}</strong></article>
        <article><span>오늘 실현손익</span>{data?.realized_pnl == null ? <strong className="neutral">-</strong> : <strong className={pnlClass(data.realized_pnl)}>{won.format(data.realized_pnl)}</strong>}</article>
        <article><span>오늘 미실현손익</span><strong className={pnlClass(unrealized)}>{won.format(unrealized)}</strong></article>
        <article><span>오늘 주문 횟수</span><strong>{orderCount}<small> 회</small></strong></article>
        <article><span>오늘 손실 제한</span><strong className={lossLimitReached ? "negative" : "positive"}>{lossLimitReached ? "주문 차단" : "여유"}</strong></article>
      </div>
    </section>
  );
}
