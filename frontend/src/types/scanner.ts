export interface ScannerCandidate {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  trade_value: number;
  vwap: number;
  volume_spike: number;
  spread_bps: number;
  score: number;
  passed: boolean;
  reasons: string[];
}

export interface ScannerResponse {
  universe_size: number;
  candidates: ScannerCandidate[];
}
