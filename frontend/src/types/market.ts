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

export type ChartPeriod = "10m" | "day" | "week" | "month";
