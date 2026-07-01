import type { ScannerResponse } from "../types/scanner";

const reasonLabels: Record<string, string> = {
  PRICE_UNAVAILABLE: "no price",
  LOW_TRADE_VALUE: "low value",
  LOW_VOLUME_SPIKE: "weak volume",
  WEAK_CHANGE_RATE: "weak move",
  OVERHEATED_CHANGE_RATE: "overheated",
  BELOW_VWAP: "below VWAP",
  WIDE_SPREAD: "wide spread",
  VI_OR_HALT_RISK: "VI/halt risk",
};

function compactKrw(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "-";
  if (value >= 1_0000_0000_0000) return `${(value / 1_0000_0000_0000).toFixed(1)}T`;
  if (value >= 1_0000_0000) return `${(value / 1_0000_0000).toFixed(0)}B`;
  return value.toLocaleString("ko-KR");
}

export function ScannerPanel({
  scanner,
  error,
  selectedSymbol,
  onSelect,
}: {
  scanner: ScannerResponse | null;
  error: string;
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
}) {
  const rows = scanner?.candidates ?? [];
  return (
    <section className="panel scanner-panel">
      <div className="panel-heading">
        <div>
          <p className="section-label">STOCK SCANNER</p>
          <h2>Large-cap active universe</h2>
        </div>
        <span className="count-badge">{scanner ? `${rows.length}/${scanner.universe_size}` : "WAIT"}</span>
      </div>
      {error ? <p className="scanner-error">{error}</p> : null}
      <div className="scanner-table">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Symbol</th>
              <th className="numeric">Score</th>
              <th className="numeric">Chg</th>
              <th className="numeric">Value</th>
              <th className="numeric">Vol x</th>
              <th className="numeric">Spread</th>
              <th>Filter</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((row, index) => (
              <tr
                className={`${row.passed ? "scanner-pass" : "scanner-watch"} ${row.symbol === selectedSymbol ? "selected" : ""}`}
                key={row.symbol}
                onClick={() => onSelect(row.symbol)}
              >
                <td>{index + 1}</td>
                <td>
                  <button type="button" className="scanner-symbol" onClick={() => onSelect(row.symbol)}>
                    <strong>{row.symbol}</strong>
                    <span>{row.name || "-"}</span>
                  </button>
                </td>
                <td className="numeric">{row.score.toFixed(1)}</td>
                <td className={`numeric ${row.change_pct >= 0 ? "positive" : "negative"}`}>{row.change_pct.toFixed(2)}%</td>
                <td className="numeric">{compactKrw(row.trade_value)}</td>
                <td className="numeric">{row.volume_spike.toFixed(2)}x</td>
                <td className="numeric">{row.spread_bps.toFixed(1)}bp</td>
                <td>
                  <span className={`scanner-state ${row.passed ? "pass" : "watch"}`}>
                    {row.passed ? "PASS" : row.reasons.map((reason) => reasonLabels[reason] ?? reason).slice(0, 2).join(", ")}
                  </span>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={8} className="empty-state">No scanner data</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
