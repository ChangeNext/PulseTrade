import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { MarketRankingResponse, RankingType } from "../types/market";

const number = new Intl.NumberFormat("ko-KR");

const RANKING_TABS: Array<{ value: RankingType; label: string }> = [
  { value: "volume", label: "거래량" },
  { value: "change", label: "등락률" },
  { value: "trade_strength", label: "체결강도" },
  { value: "quote_balance", label: "호가잔량" },
  { value: "market_cap", label: "시가총액" },
  { value: "near_high_low", label: "신고/신저" },
];

function compact(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "-";
  if (value >= 1_0000_0000_0000) return `${(value / 1_0000_0000_0000).toFixed(1)}조`;
  if (value >= 1_0000_0000) return `${(value / 1_0000_0000).toFixed(0)}억`;
  return number.format(Math.round(value));
}

export function MarketDiscoveryPanel({
  selectedSymbol,
  onSelect,
}: {
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}) {
  const [rankingType, setRankingType] = useState<RankingType>("volume");
  const [ranking, setRanking] = useState<MarketRankingResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    void api.marketRankings(rankingType)
      .then((next) => {
        if (cancelled) return;
        setRanking(next);
        setError("");
      })
      .catch((caught) => {
        if (cancelled) return;
        setRanking(null);
        setError(caught instanceof Error ? caught.message : "순위 데이터를 가져오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [rankingType]);

  return (
    <section className="panel discovery-panel">
      <div className="panel-heading">
        <div>
          <p className="section-label">MARKET DISCOVERY</p>
          <h2>시장 순위로 종목 찾기</h2>
        </div>
        <span className="count-badge">{ranking ? `${ranking.rows.length}` : "WAIT"}</span>
      </div>
      <div className="ranking-tabs discovery-tabs" role="tablist" aria-label="순위 종류">
        {RANKING_TABS.map((item) => (
          <button
            aria-selected={rankingType === item.value}
            className={rankingType === item.value ? "active" : ""}
            key={item.value}
            onClick={() => setRankingType(item.value)}
            role="tab"
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>
      {error ? <p className="scanner-error">{error}</p> : null}
      <div className="ranking-table discovery-table">
        <table>
          <thead>
            <tr>
              <th>순위</th>
              <th>종목</th>
              <th className="numeric">현재가</th>
              <th className="numeric">등락</th>
              <th className="numeric">거래량</th>
              <th className="numeric">거래대금</th>
            </tr>
          </thead>
          <tbody>
            {(ranking?.rows ?? []).length ? ranking!.rows.map((row) => (
              <tr
                className={row.symbol === selectedSymbol ? "selected" : ""}
                key={`${row.source}-${row.rank}-${row.symbol}`}
                onClick={() => onSelect(row.symbol)}
              >
                <td>{row.rank}</td>
                <td>
                  <button className="ranking-symbol" type="button" onClick={() => onSelect(row.symbol)}>
                    <strong>{row.symbol}</strong>
                    <span>{row.name || "-"}</span>
                  </button>
                </td>
                <td className="numeric">{row.price > 0 ? number.format(row.price) : "-"}</td>
                <td className={`numeric ${row.change_pct >= 0 ? "positive" : "negative"}`}>
                  {row.change_pct.toFixed(2)}%
                </td>
                <td className="numeric">{compact(row.volume)}</td>
                <td className="numeric">{compact(row.trade_value)}</td>
              </tr>
            )) : (
              <tr><td colSpan={6} className="empty-state">순위 데이터가 없습니다.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
