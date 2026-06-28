import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ChartPeriod, MarketBar, MarketQuote, StockSearchResult } from "../types/market";
import type { StrategySignalData, StrategyStatusData } from "../types/strategy";

const number = new Intl.NumberFormat("ko-KR");
const PERIODS: Array<{ value: ChartPeriod; label: string; title: string }> = [
  { value: "10m", label: "10분", title: "당일 10분봉" },
  { value: "day", label: "일봉", title: "일봉" },
  { value: "week", label: "주봉", title: "주봉" },
  { value: "month", label: "월봉", title: "월봉" },
];

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

type PivotPoint = {
  index: number;
  x: number;
  value: number;
};

type TrendLine = {
  start: [number, number];
  end: [number, number];
  price: number;
  label: [number, number];
  slope: number;
  touchCount: number;
  role: "support" | "resistance";
};

type TrendConfig = {
  lookback: number;
  candidateLookback: number;
  pivotRadius: number;
  toleranceRatio: number;
  minTouches: number;
  maxProjectionDriftRatio: number;
};

function trendConfig(period: ChartPeriod): TrendConfig {
  if (period === "week") return { lookback: 180, candidateLookback: 70, pivotRadius: 2, toleranceRatio: 0.015, minTouches: 2, maxProjectionDriftRatio: 0.45 };
  if (period === "month") return { lookback: 120, candidateLookback: 48, pivotRadius: 2, toleranceRatio: 0.02, minTouches: 2, maxProjectionDriftRatio: 0.5 };
  if (period === "day") return { lookback: 90, candidateLookback: 42, pivotRadius: 2, toleranceRatio: 0.012, minTouches: 2, maxProjectionDriftRatio: 0.38 };
  return { lookback: 90, candidateLookback: 42, pivotRadius: 2, toleranceRatio: 0.012, minTouches: 2, maxProjectionDriftRatio: 0.38 };
}

function pivotTrendLines(
  bars: MarketBar[],
  points: Array<[number, number]>,
  toY: (price: number) => number,
  xMax: number,
  config: TrendConfig,
) {
  const lows: PivotPoint[] = [];
  const highs: PivotPoint[] = [];
  bars.forEach((bar, index) => {
    if (index < config.pivotRadius || index > bars.length - config.pivotRadius - 1) return;
    const neighbors = bars.slice(index - config.pivotRadius, index + config.pivotRadius + 1);
    if (bar.low === Math.min(...neighbors.map((item) => item.low))) lows.push({ index, x: points[index]?.[0] ?? 0, value: bar.low });
    if (bar.high === Math.max(...neighbors.map((item) => item.high))) highs.push({ index, x: points[index]?.[0] ?? 0, value: bar.high });
  });

  const tolerance = Math.max((Math.max(...bars.map((item) => item.high)) - Math.min(...bars.map((item) => item.low))) * config.toleranceRatio, 1);
  const latestIndex = bars.length - 1;
  const candidateStart = Math.max(0, bars.length - config.candidateLookback);
  const priceSpan = Math.max(...bars.map((item) => item.high)) - Math.min(...bars.map((item) => item.low));
  const latestClose = bars.at(-1)?.price ?? 0;

  function projectedValue(first: PivotPoint, slope: number, x: number) {
    return first.value + slope * (x - first.x);
  }

  function lineTouches(pivots: PivotPoint[], first: PivotPoint, slope: number) {
    return pivots.filter((pivot) => Math.abs(pivot.value - projectedValue(first, slope, pivot.x)) <= tolerance);
  }

  function spacingScore(touches: PivotPoint[]) {
    if (touches.length < 3) return 0;
    const gaps = touches.slice(1).map((pivot, index) => pivot.index - touches[index].index);
    const averageGap = gaps.reduce((sum, gap) => sum + gap, 0) / gaps.length;
    const variance = gaps.reduce((sum, gap) => sum + Math.abs(gap - averageGap), 0) / gaps.length;
    return Math.max(0, 1 - variance / Math.max(averageGap, 1));
  }

  function chooseBoundaryLine(pivots: PivotPoint[], role: "support" | "resistance"): TrendLine | null {
    let best: { line: TrendLine; score: number } | null = null;
    const candidates = pivots.filter((pivot) => pivot.index >= candidateStart);
    for (let i = 0; i < candidates.length - 1; i += 1) {
      for (let j = i + 1; j < candidates.length; j += 1) {
        const first = candidates[i];
        const second = candidates[j];
        if (second.x <= first.x) continue;
        if (second.index < latestIndex - Math.floor(config.candidateLookback * 0.45)) continue;
        const slope = (second.value - first.value) / (second.x - first.x);
        if (!Number.isFinite(slope)) continue;
        const touchedPivots = lineTouches(candidates, first, slope);
        if (touchedPivots.length < config.minTouches) continue;
        const latestTouch = touchedPivots.reduce((current, pivot) => (pivot.x > current.x ? pivot : current));
        if (latestTouch.index < latestIndex - Math.floor(config.candidateLookback * 0.35)) continue;
        const projectedEndValue = projectedValue(first, slope, xMax);
        if (
          latestClose > 0
          && priceSpan > 0
          && Math.abs(projectedEndValue - latestClose) > priceSpan * config.maxProjectionDriftRatio
        ) {
          continue;
        }
        const recentBars = bars.slice(Math.max(first.index, candidateStart));
        const breaks = recentBars.filter((bar, offset) => {
          const index = Math.max(first.index, candidateStart) + offset;
          const expected = projectedValue(first, slope, points[index]?.[0] ?? first.x);
          return role === "support" ? bar.price < expected - tolerance : bar.price > expected + tolerance;
        }).length;
        if (breaks > Math.max(1, Math.floor(recentBars.length * 0.12))) continue;
        const line: TrendLine = {
          start: [first.x, toY(first.value)],
          end: [xMax, toY(projectedEndValue)],
          price: latestTouch.value,
          label: [latestTouch.x, toY(latestTouch.value) + (role === "support" ? -10 : 14)],
          slope,
          touchCount: touchedPivots.length,
          role,
        };
        const latestBonus = latestTouch.index * 100;
        const currentFitPenalty = priceSpan > 0 ? Math.abs(projectedEndValue - latestClose) / priceSpan * 500 : 0;
        const validationBonus = touchedPivots.length >= 3 ? 1600 : 0;
        const distributionBonus = spacingScore(touchedPivots) * 700;
        const breakPenalty = breaks * 900;
        const score = touchedPivots.length * 1000 + validationBonus + distributionBonus + latestBonus + (second.index - first.index) * 5 - currentFitPenalty - breakPenalty;
        if (!best || score > best.score) best = { line, score };
      }
    }
    return best?.line ?? null;
  }

  function parallelLowerChannel(upperLine: TrendLine | null): TrendLine | null {
    if (!upperLine || lows.length < 2) return null;
    let best: { pivot: PivotPoint; touches: number; score: number } | null = null;
    const recentLows = lows.filter((pivot) => pivot.index >= candidateStart);
    for (const pivot of recentLows) {
      const touches = recentLows.filter((item) => {
        const expected = pivot.value + upperLine.slope * (item.x - pivot.x);
        return Math.abs(item.value - expected) <= tolerance;
      }).length;
      if (touches < Math.max(2, config.minTouches - 1)) continue;
      const score = touches * 1000 + pivot.index;
      if (!best || score > best.score) best = { pivot, touches, score };
    }
    if (!best) return null;
    const projectedEndValue = best.pivot.value + upperLine.slope * (xMax - best.pivot.x);
    if (
      latestClose > 0
      && priceSpan > 0
      && Math.abs(projectedEndValue - latestClose) > priceSpan * config.maxProjectionDriftRatio
    ) {
      return null;
    }
    const touchedLows = recentLows.filter((item) => {
      const expected = best.pivot.value + upperLine.slope * (item.x - best.pivot.x);
      return Math.abs(item.value - expected) <= tolerance;
    });
    const latestTouch = touchedLows.reduce((current, pivot) => (pivot.x > current.x ? pivot : current), touchedLows[0]);
    return {
      start: [best.pivot.x, toY(best.pivot.value)],
      end: [xMax, toY(projectedEndValue)],
      price: latestTouch.value,
      label: [latestTouch.x, toY(latestTouch.value) - 10],
      slope: upperLine.slope,
      touchCount: touchedLows.length,
      role: "support",
    };
  }

  const support = chooseBoundaryLine(lows, "support");
  const resistance = chooseBoundaryLine(highs, "resistance");

  return {
    support,
    resistance,
    lowerChannel: parallelLowerChannel(resistance),
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

function CandleChart({ bars, period }: { bars: MarketBar[]; period: ChartPeriod }) {
  const width = 980;
  const height = 420;
  const paddingTop = 18;
  const paddingLeft = 22;
  const paddingRight = 82;
  const paddingBottom = 44;
  const volumeHeight = 88;
  const priceBottom = height - paddingBottom - volumeHeight - 12;
  const volumeTop = height - paddingBottom - volumeHeight;
  const volumeBase = height - paddingBottom;
  const usableWidth = width - paddingLeft - paddingRight;
  const usableHeight = priceBottom - paddingTop;
  const config = trendConfig(period);
  const sliced = bars.slice(-config.lookback);
  const prices = sliced.flatMap((bar) => [bar.open, bar.high, bar.low, bar.price]).filter((value) => value > 0);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(max - min, 1);
  const candles = sliced.map((bar, index) => {
    const x = paddingLeft + (sliced.length <= 1 ? 0 : (index / (sliced.length - 1)) * usableWidth);
    const openY = paddingTop + ((max - bar.open) / span) * usableHeight;
    const closeY = paddingTop + ((max - bar.price) / span) * usableHeight;
    const highY = paddingTop + ((max - bar.high) / span) * usableHeight;
    const lowY = paddingTop + ((max - bar.low) / span) * usableHeight;
    return { x, openY, closeY, highY, lowY, open: bar.open, close: bar.price, time: bar.time };
  });
  const volumeMax = Math.max(...sliced.map((bar) => bar.volume), 1);
  const levels = nearestLevels(sliced);
  const levelY = (price: number) => paddingTop + ((max - price) / span) * usableHeight;
  const showLevels = period === "day" || period === "week" || period === "month";
  const trendLines = pivotTrendLines(sliced, candles.map((candle) => [candle.x, candle.closeY] as [number, number]), levelY, width - paddingRight, config);
  const ticks = axisTicks(min, max);
  const times = timeTicks(sliced, candles.map((candle) => [candle.x, candle.closeY] as [number, number]), period);

  if (sliced.length < 2) {
    return <div className="chart-empty">분봉 데이터를 기다리는 중입니다.</div>;
  }

  return (
    <svg className="market-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${PERIODS.find((item) => item.value === period)?.title ?? "차트"} 가격 차트`}>
      {[0, 1, 2, 3].map((line) => {
        const y = paddingTop + (line / 3) * usableHeight;
        return <line className="chart-grid" key={line} x1={paddingLeft} x2={width - paddingRight} y1={y} y2={y} />;
      })}
      <rect className="volume-zone" x={paddingLeft} y={volumeTop} width={usableWidth} height={volumeHeight} rx="6" />
      {candles.map((candle, index) => {
        const bodyTop = Math.min(candle.openY, candle.closeY);
        const bodyHeight = Math.max(Math.abs(candle.closeY - candle.openY), 1.5);
        const bodyWidth = Math.max(sliced.length > 40 ? 4 : sliced.length > 20 ? 6 : 9, 2);
        const bullish = candle.close >= candle.open;
        const sourceBar = sliced[index];
        const h = Math.max((sourceBar.volume / volumeMax) * (volumeHeight - 8), 1);
        return (
          <g key={`${candle.time}-${index}`}>
            <line
              className={`candle-wick ${bullish ? "bull" : "bear"}`}
              x1={candle.x}
              x2={candle.x}
              y1={candle.highY}
              y2={candle.lowY}
            />
            <rect
              className={`candle-body ${bullish ? "bull" : "bear"}`}
              x={candle.x - bodyWidth / 2}
              y={bodyTop}
              width={bodyWidth}
              height={bodyHeight}
              rx="1.5"
            />
            <rect className="volume-bar" x={candle.x - 2} y={volumeBase - h} width="3" height={h} />
          </g>
        );
      })}
      <line className="volume-baseline" x1={paddingLeft} x2={width - paddingRight} y1={volumeBase} y2={volumeBase} />
      {trendLines.support && (
        <g>
          <line
            className="trend-line support"
            x1={trendLines.support.start[0]}
            x2={trendLines.support.end[0]}
            y1={trendLines.support.start[1]}
            y2={trendLines.support.end[1]}
          />
          <g transform={`translate(${trendLines.support.label[0]}, ${trendLines.support.label[1]})`}>
            <rect className="trend-label-bg support" x="-32" y="-11" width="64" height="18" rx="4" />
            <text className="trend-label support" textAnchor="middle" dominantBaseline="middle">
              S {number.format(Math.round(trendLines.support.price))}
            </text>
          </g>
        </g>
      )}
      {trendLines.resistance && (
        <g>
          <line
            className="trend-line resistance"
            x1={trendLines.resistance.start[0]}
            x2={trendLines.resistance.end[0]}
            y1={trendLines.resistance.start[1]}
            y2={trendLines.resistance.end[1]}
          />
          <g transform={`translate(${trendLines.resistance.label[0]}, ${trendLines.resistance.label[1]})`}>
            <rect className="trend-label-bg resistance" x="-32" y="-11" width="64" height="18" rx="4" />
            <text className="trend-label resistance" textAnchor="middle" dominantBaseline="middle">
              R {number.format(Math.round(trendLines.resistance.price))}
            </text>
          </g>
        </g>
      )}
      {trendLines.lowerChannel && (
        <g>
          <line
            className="trend-line lower-channel"
            x1={trendLines.lowerChannel.start[0]}
            x2={trendLines.lowerChannel.end[0]}
            y1={trendLines.lowerChannel.start[1]}
            y2={trendLines.lowerChannel.end[1]}
          />
          <g transform={`translate(${trendLines.lowerChannel.label[0]}, ${trendLines.lowerChannel.label[1]})`}>
            <rect className="trend-label-bg lower-channel" x="-28" y="-11" width="56" height="18" rx="4" />
            <text className="trend-label lower-channel" textAnchor="middle" dominantBaseline="middle">
              {number.format(Math.round(trendLines.lowerChannel.price))}
            </text>
          </g>
        </g>
      )}
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
  selectedSymbol,
  onPeriodChange,
  onSymbolChange,
}: {
  quote: MarketQuote | null;
  bars: MarketBar[];
  strategy: StrategyStatusData | null;
  error: string;
  period: ChartPeriod;
  selectedSymbol: string;
  onPeriodChange: (period: ChartPeriod) => void;
  onSymbolChange: (symbol: string) => void;
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [searchError, setSearchError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [calculatedSignal, setCalculatedSignal] = useState<StrategySignalData | null>(null);
  const [scoreError, setScoreError] = useState("");
  const [scoreLoading, setScoreLoading] = useState(false);
  const symbol = quote?.symbol ?? selectedSymbol ?? strategy?.watched_symbols?.[0] ?? "005930";
  const watchedSignal = strategy?.signals?.find((item) => item.symbol === symbol);
  const signal = calculatedSignal?.symbol === symbol ? calculatedSignal : watchedSignal;
  const previous = bars.length > 1 ? bars.at(-2)?.price ?? 0 : 0;
  const current = quote?.price ?? bars.at(-1)?.price ?? 0;
  const change = previous > 0 ? ((current - previous) / previous) * 100 : 0;
  const periodTitle = PERIODS.find((item) => item.value === period)?.title ?? "차트";
  const sliced = bars.slice(-90);
  const chartHigh = sliced.length > 0 ? Math.max(...sliced.map((bar) => bar.high)) : 0;
  const chartLow = sliced.length > 0 ? Math.min(...sliced.map((bar) => bar.low)) : 0;
  const chartRangePct = chartLow > 0 && chartHigh > chartLow ? ((chartHigh - chartLow) / chartLow) * 100 : 0;
  const lastVolume = sliced.at(-1)?.volume ?? 0;
  const averageVolume = sliced.length > 0 ? sliced.reduce((sum, bar) => sum + bar.volume, 0) / sliced.length : 0;
  const volumeRatio = averageVolume > 0 ? lastVolume / averageVolume : 0;
  const levels = nearestLevels(sliced);
  const supportLabel = levels.support ? `S ${number.format(Math.round(levels.support))}` : "S -";
  const resistanceLabel = levels.resistance ? `R ${number.format(Math.round(levels.resistance))}` : "R -";
  const signalLabel = signal ? `${signal.action} ${Number(signal.score).toFixed(1)}` : scoreLoading ? "SCORING" : "NO SIGNAL";

  useEffect(() => {
    const query = searchTerm.trim();
    if (query.length < 1) {
      setResults([]);
      setSearchError("");
      setHasSearched(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void api.stockSearch(query)
        .then((items) => {
          setResults(items);
          setSearchError("");
          setHasSearched(true);
        })
        .catch((caught) => {
          setResults([]);
          setSearchError(caught instanceof Error ? caught.message : "종목 검색에 실패했습니다.");
          setHasSearched(true);
        });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    if (!symbol || !/^\d{6}$/.test(symbol)) return;
    let cancelled = false;
    setScoreLoading(true);
    setScoreError("");
    void api.strategyScore(symbol)
      .then((nextSignal) => {
        if (cancelled) return;
        setCalculatedSignal(nextSignal);
        setScoreError("");
      })
      .catch((caught) => {
        if (cancelled) return;
        setCalculatedSignal(null);
        setScoreError(caught instanceof Error ? caught.message : "전략 점수 계산에 실패했습니다.");
      })
      .finally(() => {
        if (!cancelled) setScoreLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  function selectStock(stock: StockSearchResult) {
    onSymbolChange(stock.symbol);
    setSearchTerm(stock.name);
    setResults([]);
    setHasSearched(false);
  }

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
        <div className="stock-search">
          <input
            aria-label="종목 검색"
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="종목명 또는 코드 검색"
            type="search"
            value={searchTerm}
          />
          {(results.length > 0 || searchError || (hasSearched && searchTerm.trim())) && (
            <div className="stock-search-results">
              {searchError && <p>{searchError}</p>}
              {!searchError && results.length === 0 && <p>검색 결과가 없습니다.</p>}
              {results.map((stock) => (
                <button key={stock.symbol} onClick={() => selectStock(stock)} type="button">
                  <strong>{stock.name}</strong>
                  <span>{stock.symbol}</span>
                  <em>{stock.market}</em>
                </button>
              ))}
            </div>
          )}
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
          {error ? <div className="chart-empty error">{error}</div> : <CandleChart bars={bars} period={period} />}
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
          <div className="chart-insights" aria-label="차트 보조 지표">
            <div>
              <span>범위</span>
              <strong>{chartLow > 0 && chartHigh > 0 ? `${number.format(Math.round(chartLow))} - ${number.format(Math.round(chartHigh))}` : "-"}</strong>
              <em>{chartRangePct > 0 ? `${chartRangePct.toFixed(2)}%` : "대기"}</em>
            </div>
            <div>
              <span>거래량</span>
              <strong>{lastVolume > 0 ? number.format(lastVolume) : "-"}</strong>
              <em>{volumeRatio > 0 ? `평균 ${volumeRatio.toFixed(1)}x` : "대기"}</em>
            </div>
            <div>
              <span>지지 / 저항</span>
              <strong>{supportLabel} · {resistanceLabel}</strong>
              <em>{periodTitle}</em>
            </div>
            <div>
              <span>전략 점수</span>
              <strong className={signal ? scoreTone(signal.action) : "neutral"}>{signalLabel}</strong>
              <em>{scoreLoading ? "전략 점수 계산 중" : scoreError || signal?.reason || "전략 신호 대기"}</em>
            </div>
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
            {!signal && <p className="component-empty">{scoreLoading ? "검색 종목의 전략 점수를 계산 중입니다." : scoreError || "전략 점수는 시세 데이터가 준비되면 표시됩니다."}</p>}
          </div>
        </aside>
      </div>
    </section>
  );
}
