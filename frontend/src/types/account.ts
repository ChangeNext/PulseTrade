export interface AccountSummaryData {
  cash: number;
  total_value: number;
  realized_pnl: number | null;
  unrealized_pnl?: number;
  daily_order_count?: number;
  daily_loss_limit_reached?: boolean;
}

export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  average_price: number;
  current_price: number;
  evaluation_pnl?: number;
  return_rate?: number;
}
