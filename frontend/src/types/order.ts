export type OrderState =
  | "SIGNAL"
  | "RISK_CHECKED"
  | "ORDER_REQUESTED"
  | "ORDER_SENT"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "CANCEL_REQUESTED"
  | "CANCELED"
  | "REJECTED"
  | "ERROR";

export interface Order {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  mode: string;
  state: OrderState;
  message: string;
  created_at: string;
}

export interface ManualOrderInput {
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  live_confirmation?: string;
}

