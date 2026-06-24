import type { AccountSummaryData, Position } from "../types/account";
import type { ManualOrderInput, Order } from "../types/order";
import type { HealthStatus, StrategyStatusData } from "../types/strategy";

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
  strategy: () => request<StrategyStatusData>("/strategy"),
  submitOrder: (order: ManualOrderInput) =>
    request<{ order_id: string; state: string; message: string }>("/orders/manual", {
      method: "POST",
      body: JSON.stringify(order),
    }),
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
