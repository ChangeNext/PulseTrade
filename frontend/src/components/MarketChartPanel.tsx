import type { ChartPeriod, MarketBar, MarketQuote } from "../types/market";
import type { StrategyStatusData } from "../types/strategy";

const number = new Intl.NumberFormat("ko-KR");
const PERIODS: Array<{ value: ChartPeriod; label: string; title: string }> = [
  { value: "10m", label: "10분", title: "당일 10분봉" },
  { value: "day", label: "일봉", title: "일봉" },
  { value: "week", label: "주봉", title: "주봉" },
  { value: "month", label: "월봉", title: "월봉" },
];

function pathFromPoints(points: Array<[number, number]>) {
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
}

function nearestLevels(bars: MarketBar[]) {
  const current = bars.at(-1)?.price ?? 0;
  if (current <= 0) return { support: null as number | null, resistance: null as number | null };
  const support = Math.max(...bars.map((bar) => bar.low).filter((value) => value > 0 && value < current));
  const resistance = Math.min(...bars.map((bar) => bar.high).filter((value) => value > current));
  return {
    support: Number.isFinite(support) ? support : null,
    resistance: Number.isFinite(resistance) ? resistance : null,
  };
}

function axisTicks(min: number, max: number) {
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => max - (max - min) * ratio);
}

function pivotTrendLines(bars: MarketBar[], points: Array<[number, number]>) {
  const lows: Array<{ index: number; value: number }> = [];
  const highs: Array<{ index: number; value: number }> = [];
  bars.forEach((bar, index) => {
    if (index < 2 || index > bars.length - 3) return;
    const neighbors = bars.slice(index - 2, index + 3);
    if (bar.low === Math.min(...neighbors.map((item) => item.low))) lows.push({ index, value: bar.low });
    if (bar.high === Math.max(...neighbors.map((item) => item.high))) highs.push({ index, value: bar.high });
  });
  const risingPair = lows
    .flatMap((first, firstIndex) => lows.slice(firstIndex + 1).map((second) => [first, second] as const))
    .filter(([first, second]) => second.value > first.value)
    .at(-1);
  const fallingPair = highs
    .flatMap((first, firstIndex) => highs.slice(firstIndex + 1).map((second) => [first, second] as const))
    .filter(([first, second]) => second.value < first.value)
    .at(-1);
  return {
    rising: risingPair ? { start: points[risingPair[0].index], end: points[risingPair[1].index] } : null,
    falling: fallingPair ? { start: points[fallingPair[0].index], end: points[fallingPair[1].index] } : null,
  };
}

function timeTicks(bars: MarketBar[], points: Array<[number, number]>, period: ChartPeriod) {
  const result: Array<{ label: string; x: number }> = [];
  let previousLabel = "";
  bars.forEach((bar, index) => {
    let label = "";
    if (period === "10m" && bar.time.length >= 4) {
      label = `${bar.time.slice(0, 2)}:${bar.time.slice(2, 4)}`;
    } else if (bar.time.length === 8 && period === "day") {
      label = `${Number(bar.time.slice(4, 6))}월`;
    } else if (bar.time.length === 8 && period === "week") {
      label = `${bar.time.slice(2, 4)}.${bar.time.slice(4, 6)}`;
    } else if (bar.time.length === 8 && period === "month") {
      label = `${bar.time.slice(0, 4)}`;
    }
    if (!label || label === previousLabel) return;
    previousLabel = label;
    result.push({ label, x: points[index]?.[0] ?? 0 });
  });
  return result.slice(period === "10m" ? -5 : -6);
}

function LineChart({ bars, period }: { bars: MarketBar[]; period: ChartPeriod }) {
  const width = 980;
  const height = 360;
  const paddingTop = 18;
  const paddingLeft = 22;
  const paddingRight = 82;
  const paddingBottom = 34;
  const volumeHeight = 72;
  const priceBottom = height - paddingBottom - volumeHeight - 10;
  const volumeTop = height - paddingBottom - volumeHeight;
  const volumeBase = height - paddingBottom;
  const usableWidth = width - paddingLeft - paddingRight;
  const usableHeight = priceBottom - paddingTop;
  const sliced = bars.slice(-90);
  const prices = sliced.flatMap((bar) => [bar.high, bar.low, bar.price]).filter((value) => value > 0);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(max - min, 1);
  const points = sliced.map((bar, index) => {
    const x = paddingLeft + (sliced.length <= 1 ? 0 : (index / (sliced.length - 1)) * usableWidth);
    const y = paddingTop + ((max - bar.price) / span) * usableHeight;
    return [x, y] as [number, number];
  });
  const volumeMax = Math.max(...sliced.map((bar) => bar.volume), 1);
  const last = sliced.at(-1);
  const levels = nearestLevels(sliced);
  const levelY = (price: number) => paddingTop + ((max - price) / span) * usableHeight;
  const showLevels = period === "day" || period === "week" || period === "month";
  const trendLines = pivotTrendLines(sliced, points);
  const ticks = axisTicks(min, max);
  const times = timeTicks(sliced, points, period);

  if (sliced.length < 2) {
    return <div className="chart-empty">분봉 데이터를 기다리는 중입니다.</div>;
  }

  return (
    <svg className="market-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${PERIODS.find((item) => item.value === period)?.title ?? "차트"} 가격 차트`}>
      <defs>
        <linearGradient id="priceFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#2bd6a2" stopOpacity="0.24" />
          <stop offset="100%" stopColor="#2bd6a2" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((line) => {
        const y = paddingTop + (line / 3) * usableHeight;
        return <line className="chart-grid" key={line} x1={paddingLeft} x2={width - paddingRight} y1={y} y2={y} />;
      })}
      <rect className="volume-zone" x={paddingLeft} y={volumeTop} width={usableWidth} height={volumeHeight} rx="6" />
      {sliced.map((bar, index) => {
        const x = paddingLeft + (sliced.length <= 1 ? 0 : (index / (sliced.length - 1)) * usableWidth);
        const h = Math.max((bar.volume / volumeMax) * (volumeHeight - 8), 1);
        return <rect className="volume-bar" key={`${bar.time}-${index}`} x={x - 2} y={volumeBase - h} width="3" height={h} />;
      })}
      <line className="volume-baseline" x1={paddingLeft} x2={width - paddingRight} y1={volumeBase} y2={volumeBase} />
      <path className="price-area" d={`${pathFromPoints(points)} L ${points.at(-1)?.[0] ?? paddingLeft} ${priceBottom} L ${paddingLeft} ${priceBottom} Z`} />
      {trendLines.rising && (
        <line
          className="trend-line rising"
          x1={trendLines.rising.start[0]}
          x2={trendLines.rising.end[0]}
          y1={trendLines.rising.start[1]}
          y2={trendLines.rising.end[1]}
        />
      )}
      {trendLines.falling && (
        <line
          className="trend-line falling"
          x1={trendLines.falling.start[0]}
          x2={trendLines.falling.end[0]}
          y1={trendLines.falling.start[1]}
          y2={trendLines.falling.end[1]}
        />
      )}
      <path className="price-line" d={pathFromPoints(points)} />
      {showLevels && levels.resistance && (
        <g>
          <line className="resistance-line" x1={paddingLeft} x2={width - paddingRight} y1={levelY(levels.resistance)} y2={levelY(levels.resistance)} />
          <text className="level-label resistance" x={paddingLeft + 8} y={levelY(levels.resistance) - 6}>R {number.format(levels.resistance)}</text>
        </g>
      )}
      {showLevels && levels.support && (
        <g>
          <line className="support-line" x1={paddingLeft} x2={width - paddingRight} y1={levelY(levels.support)} y2={levelY(levels.support)} />
          <text className="level-label support" x={paddingLeft + 8} y={levelY(levels.support) + 14}>S {number.format(levels.support)}</text>
        </g>
      )}
      {ticks.map((tick, index) => (
        <text className="price-axis-label" key={`${index}-${tick}`} x={width - 12} y={levelY(tick) + 4} textAnchor="end">{number.format(Math.round(tick))}</text>
      ))}
      {times.map((time) => (
        <text className="time-axis-label" key={`${time.label}-${time.x}`} x={time.x} y={height - 12} textAnchor="middle">{time.label}</text>
      ))}
      {last && <circle className="price-dot" cx={points.at(-1)?.[0]} cy={points.at(-1)?.[1]} r="4" />}
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
    price_location: "가격 위치",
    trend_structure: "추세 구조",
    breakout_confirmation: "돌파",
    pullback_quality: "눌림목",
    moving_average_alignment: "이평 배열",
    candle_quality: "캔들",
    momentum_indicators: "MACD/RSI",
    risk_reward: "손익비",
    market_regime: "시장 지표",
  } as Record<string, string>)[name] ?? name;
}

function formatBarTime(value: string, period: ChartPeriod) {
  if (!value) return "대기";
  if (period === "10m") return `${value.slice(0, 2)}:${value.slice(2, 4)}`;
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
          {error ? <div className="chart-empty error">{error}</div> : <LineChart bars={bars} period={period} />}
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
