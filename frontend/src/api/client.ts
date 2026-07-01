import type { AccountSummaryData, Position } from "../types/account";
import type {
  ChartPeriod,
  MarketBar,
  MarketQuote,
  MarketRankingResponse,
  OrderBookView,
  RankingType,
  StockSearchResult,
} from "../types/market";
import type { ManualOrderInput, Order } from "../types/order";
import type { ScannerResponse } from "../types/scanner";
import type { HealthStatus, StrategySignalData, StrategyStatusData } from "../types/strategy";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>("/health"),
  account: async () => {
    const data = await request<AccountSummaryData>("/account");
    return {
      ...data,
      cash: Number(data.cash),
      total_value: Number(data.total_value),
      realized_pnl: data.realized_pnl == null ? null : Number(data.realized_pnl),
      unrealized_pnl: Number(data.unrealized_pnl ?? 0),
    };
  },
  positions: async () => {
    const positions = await request<Position[]>("/positions");
    return positions.map((position) => ({
      ...position,
      quantity: Number(position.quantity),
      average_price: Number(position.average_price),
      current_price: Number(position.current_price),
      evaluation_pnl: Number(position.evaluation_pnl ?? 0),
      return_rate: Number(position.return_rate ?? 0),
    }));
  },
  orders: () => request<Order[]>("/orders"),
  marketQuote: async (symbol: string) => {
    const quote = await request<MarketQuote>(`/market/${symbol}`);
    return {
      ...quote,
      price: Number(quote.price),
      volume: Number(quote.volume),
    };
  },
  marketBars: async (symbol: string, period: ChartPeriod) => {
    const bars = await request<MarketBar[]>(`/market/${symbol}/bars?period=${period}`);
    return bars.map((bar) => ({
      ...bar,
      open: Number(bar.open),
      price: Number(bar.price),
      high: Number(bar.high),
      low: Number(bar.low),
      volume: Number(bar.volume),
    }));
  },
  marketOrderbook: async (symbol: string) => {
    const book = await request<OrderBookView>(`/market/${symbol}/orderbook`);
    return {
      ...book,
      best_ask: Number(book.best_ask),
      best_bid: Number(book.best_bid),
      total_ask_quantity: Number(book.total_ask_quantity),
      total_bid_quantity: Number(book.total_bid_quantity),
      best_ask_quantity: Number(book.best_ask_quantity),
      best_bid_quantity: Number(book.best_bid_quantity),
      spread_bps: Number(book.spread_bps),
      imbalance: Number(book.imbalance),
    };
  },
  marketRankings: async (type: RankingType) => {
    const result = await request<MarketRankingResponse>(`/market/rankings?type=${type}&limit=20`);
    return {
      ...result,
      rows: result.rows.map((row) => ({
        ...row,
        price: Number(row.price),
        change_pct: Number(row.change_pct),
        volume: Number(row.volume),
        trade_value: Number(row.trade_value),
        score: Number(row.score),
      })),
    };
  },
  stockSearch: (query: string) =>
    request<StockSearchResult[]>(`/stocks/search?q=${encodeURIComponent(query)}&limit=12`),
  scannerCandidates: async () => {
    const result = await request<ScannerResponse>("/scanner/candidates");
    return {
      ...result,
      candidates: result.candidates.map((candidate) => ({
        ...candidate,
        price: Number(candidate.price),
        change_pct: Number(candidate.change_pct),
        volume: Number(candidate.volume),
        trade_value: Number(candidate.trade_value),
        vwap: Number(candidate.vwap),
        volume_spike: Number(candidate.volume_spike),
        spread_bps: Number(candidate.spread_bps),
        score: Number(candidate.score),
      })),
    };
  },
  strategy: () => request<StrategyStatusData>("/strategy"),
  strategyScore: (symbol: string) => request<StrategySignalData>(`/strategy/${symbol}/score`),
  submitOrder: (order: ManualOrderInput) =>
    request<{ order_id: string; state: string; message: string }>("/orders/manual", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(order),
    }),
  cancelOrder: (orderId: string) =>
    request<{ order_id: string; state: string; message: string }>(`/orders/${orderId}/cancel`, {
      method: "POST",
    }),
  reconcile: () => request<{ account_synced: boolean; orders_synced: boolean }>("/control/reconcile", { method: "POST" }),
  setAutomation: (enabled: boolean) =>
    request<{ enabled: boolean; message?: string }>("/control/automation", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  setKillSwitch: (stopped: boolean) =>
    request<{ emergency_stopped: boolean }>("/control/kill-switch", {
      method: "POST",
      body: JSON.stringify({ stopped }),
    }),
};
