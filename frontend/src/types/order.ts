export type OrderState =
  | "SIGNAL"
  | "RISK_CHECKED"
  | "ORDER_REQUESTED"
  | "ORDER_SENT"
  | "RECONCILING"
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
  filled_quantity: number;
  average_fill_price: number | null;
  broker_order_id: string | null;
  source: "MANUAL" | "STRATEGY" | "EXIT" | "RECOVERY";
  commission: number;
  tax: number;
  reprice_count: number;
  mode: string;
  state: OrderState;
  message: string;
  created_at: string;
  updated_at: string;
}

export interface ManualOrderInput {
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  live_confirmation?: string;
}
