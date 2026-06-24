import type { Position } from "../types/account";

const number = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });

export function PositionTable({ positions }: { positions: Position[] }) {
  return (
    <section className="panel table-panel positions-panel">
      <div className="panel-heading"><div><p className="section-label">POSITIONS</p><h2>보유 종목</h2></div><span className="count-badge">{positions.length} 종목</span></div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>종목코드</th><th>종목명</th><th className="numeric">보유수량</th><th className="numeric">평균단가</th><th className="numeric">현재가</th><th className="numeric">평가손익</th><th className="numeric">수익률</th></tr></thead>
          <tbody>
            {positions.length ? positions.map((position) => {
              const pnl = position.evaluation_pnl ?? (position.current_price - position.average_price) * position.quantity;
              const rate = position.return_rate ?? (position.average_price ? ((position.current_price / position.average_price) - 1) * 100 : 0);
              const tone = pnl > 0 ? "positive" : pnl < 0 ? "negative" : "neutral";
              return <tr key={position.symbol}>
                <td className="symbol-cell">{position.symbol}</td><td>{position.name || "-"}</td><td className="numeric">{number.format(position.quantity)}</td><td className="numeric">{number.format(position.average_price)}</td><td className="numeric">{number.format(position.current_price)}</td><td className={`numeric ${tone}`}>{number.format(pnl)}</td><td className={`numeric ${tone}`}>{rate > 0 ? "+" : ""}{rate.toFixed(2)}%</td>
              </tr>;
            }) : <tr><td colSpan={7} className="empty-state">현재 보유 중인 종목이 없습니다.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}

