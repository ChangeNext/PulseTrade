export interface MarketQuote {
  symbol: string;
  name: string;
  price: number;
  volume: number;
}

export interface MarketBar {
  time: string;
  price: number;
  high: number;
  low: number;
  volume: number;
}

export type ChartPeriod = "10m" | "day" | "week" | "month";
