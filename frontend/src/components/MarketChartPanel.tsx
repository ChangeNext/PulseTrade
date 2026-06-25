import type { ChartPeriod, MarketBar, MarketQuote } from "../types/market";
import type { StrategyStatusData } from "../types/strategy";

const number = new Intl.NumberFormat("ko-KR");
const PERIODS: Array<{ value: ChartPeriod; label: string; title: string }> = [
  { value: "1m", label: "1분", title: "당일 1분봉" },
  { value: "day", label: "일봉", title: "일봉" },
  { value: "week", label: "주봉", title: "주봉" },
  { value: "month", label: "월봉", title: "월봉" },
];

function pathFromPoints(points: Array<[number, number]>) {
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
}

function LineChart({ bars }: { bars: MarketBar[] }) {
  const width = 720;
  const height = 260;
  const padding = 18;
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  const sliced = bars.slice(-90);
  const prices = sliced.flatMap((bar) => [bar.high, bar.low, bar.price]).filter((value) => value > 0);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(max - min, 1);
  const points = sliced.map((bar, index) => {
    const x = padding + (sliced.length <= 1 ? 0 : (index / (sliced.length - 1)) * usableWidth);
    const y = padding + ((max - bar.price) / span) * usableHeight;
    return [x, y] as [number, number];
  });
  const volumeMax = Math.max(...sliced.map((bar) => bar.volume), 1);
  const last = sliced.at(-1);

  if (sliced.length < 2) {
    return <div className="chart-empty">분봉 데이터를 기다리는 중입니다.</div>;
  }

  return (
    <svg className="market-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="당일 1분봉 가격 차트">
      <defs>
        <linearGradient id="priceFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#2bd6a2" stopOpacity="0.24" />
          <stop offset="100%" stopColor="#2bd6a2" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((line) => {
        const y = padding + (line / 3) * usableHeight;
        return <line className="chart-grid" key={line} x1={padding} x2={width - padding} y1={y} y2={y} />;
      })}
      {sliced.map((bar, index) => {
        const x = padding + (sliced.length <= 1 ? 0 : (index / (sliced.length - 1)) * usableWidth);
        const h = Math.max((bar.volume / volumeMax) * 48, 1);
        return <rect className="volume-bar" key={`${bar.time}-${index}`} x={x - 2} y={height - padding - h} width="3" height={h} />;
      })}
      <path className="price-area" d={`${pathFromPoints(points)} L ${points.at(-1)?.[0] ?? padding} ${height - padding} L ${padding} ${height - padding} Z`} />
      <path className="price-line" d={pathFromPoints(points)} />
      {last && <circle className="price-dot" cx={points.at(-1)?.[0]} cy={points.at(-1)?.[1]} r="4" />}
      <text className="chart-label high" x={width - padding} y={padding + 4} textAnchor="end">{number.format(max)}</text>
      <text className="chart-label low" x={width - padding} y={height - padding - 4} textAnchor="end">{number.format(min)}</text>
    </svg>
  );
}

function scoreTone(action?: string) {
  if (action === "BUY") return "buy";
  if (action === "SELL" || action === "EXIT") return "sell";
  return "wait";
}

function componentLabel(name: string) {
  return ({
    opening_range_breakout: "ORB",
    volume_spike: "거래량",
    vwap: "VWAP",
    orderbook_imbalance: "호가",
    trade_strength: "체결강도",
    momentum: "모멘텀",
    trend_alignment: "추세",
  } as Record<string, string>)[name] ?? name;
}

function formatBarTime(value: string, period: ChartPeriod) {
  if (!value) return "대기";
  if (period === "1m") return `${value.slice(0, 2)}:${value.slice(2, 4)}`;
  if (value.length !== 8) return value;
  return `${value.slice(2, 4)}.${value.slice(4, 6)}.${value.slice(6, 8)}`;
}

export function MarketChartPanel({
  quote,
  bars,
  strategy,
  error,
  period,
  onPeriodChange,
}: {
  quote: MarketQuote | null;
  bars: MarketBar[];
  strategy: StrategyStatusData | null;
  error: string;
  period: ChartPeriod;
  onPeriodChange: (period: ChartPeriod) => void;
}) {
  const symbol = quote?.symbol ?? strategy?.watched_symbols?.[0] ?? "005930";
  const signal = strategy?.signals?.find((item) => item.symbol === symbol) ?? strategy?.signals?.[0];
  const previous = bars.length > 1 ? bars.at(-2)?.price ?? 0 : 0;
  const current = quote?.price ?? bars.at(-1)?.price ?? 0;
  const change = previous > 0 ? ((current - previous) / previous) * 100 : 0;
  const periodTitle = PERIODS.find((item) => item.value === period)?.title ?? "차트";

  return (
    <section className="market-panel">
      <div className="market-hero">
        <div>
          <p className="section-label">WATCHED SYMBOL</p>
          <div className="quote-title">
            <h2>{quote?.name || "종목명 확인 중"}</h2>
            <span>{symbol}</span>
          </div>
        </div>
        <div className="quote-price">
          <strong>{current > 0 ? number.format(current) : "-"}</strong>
          <span className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>
        </div>
      </div>
      <div className="market-grid">
        <div className="chart-surface">
          <div className="chart-toolbar">
            <span>{periodTitle}</span>
            <em>{formatBarTime(bars.at(-1)?.time ?? "", period)}</em>
          </div>
          {error ? <div className="chart-empty error">{error}</div> : <LineChart bars={bars} />}
          <div className="period-control" role="tablist" aria-label="차트 기간">
            {PERIODS.map((item) => (
              <button
                aria-selected={period === item.value}
                className={period === item.value ? "active" : ""}
                key={item.value}
                onClick={() => onPeriodChange(item.value)}
                role="tab"
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <aside className="score-deck">
          <div className={`score-card score-${scoreTone(signal?.action)}`}>
            <span>전략 점수</span>
            <strong>{signal ? Number(signal.score).toFixed(1) : "0.0"}</strong>
            <em>{signal?.action ?? "WAIT"}</em>
          </div>
          <div className="score-rules">
            <div><span>BUY</span><strong>70점 이상</strong></div>
            <div><span>SELL</span><strong>-60점 이하</strong></div>
            <div><span>EXIT</span><strong>-80점 이하</strong></div>
            <div><span>WAIT</span><strong>그 외 구간</strong></div>
          </div>
          <div className="component-list">
            {(signal?.components ?? []).map((component) => (
              <div className="component-row" key={component.name}>
                <div><strong>{componentLabel(component.name)}</strong><span>{component.ready ? "READY" : "WAIT"}</span></div>
                <meter min={-100} max={100} low={-60} high={70} optimum={80} value={component.score} />
                <em>{Number(component.score).toFixed(0)}</em>
              </div>
            ))}
            {!signal && <p className="component-empty">전략 점수는 실시간 데이터가 준비되면 표시됩니다.</p>}
          </div>
        </aside>
      </div>
    </section>
  );
}
