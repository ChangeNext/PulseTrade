export interface MarketQuote {
  symbol: string;
  name: string;
  price: number;
  volume: number;
}

export interface MarketBar {
  time: string;
  open: number;
  price: number;
  high: number;
  low: number;
  volume: number;
}

export interface StockSearchResult {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  product: string;
}

export interface OrderBookView {
  symbol: string;
  best_ask: number;
  best_bid: number;
  total_ask_quantity: number;
  total_bid_quantity: number;
  best_ask_quantity: number;
  best_bid_quantity: number;
  spread_bps: number;
  imbalance: number;
  received_at: string | null;
  source: string;
}

export type RankingType =
  | "volume"
  | "change"
  | "trade_strength"
  | "quote_balance"
  | "market_cap"
  | "near_high_low";

export interface MarketRankingRow {
  rank: number;
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  trade_value: number;
  score: number;
  source: string;
}

export interface MarketRankingResponse {
  type: RankingType;
  rows: MarketRankingRow[];
}

export type ChartPeriod = "10m" | "day" | "week" | "month";
