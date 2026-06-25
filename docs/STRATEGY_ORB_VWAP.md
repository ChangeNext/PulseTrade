# ORB + VWAP + Volume Strategy

The live strategy score is a weighted composite of market-data components. Each
component returns a normalized score from -100 to 100. `SignalScorer` combines
ready components by configured weights, then applies the risk filter before any
entry signal can become an order.

Default component weights:

- Opening range breakout: 25
- 1-minute relative volume: 20
- VWAP distance: 15
- Order book imbalance: 15
- Realtime trade strength: 15
- 5-minute momentum: 10
- Trend alignment: 10

Default decision thresholds:

- `BUY`: composite score >= 70 and risk filter passes
- `SELL`: held position score <= -60
- `EXIT`: held position score <= -80
- `WAIT`: every other state, including missing required data

The trend-alignment component uses recent 1-minute closes to compare the 5-bar
average with the 20-bar average, measure the 20-bar average slope, and penalize
very extended moves above the 20-bar average. This is intended to reward cleaner
chart structure without treating a single price jump as a full signal.

Risk gates still run after scoring. The strategy will not enter when a position
is already held, an order is pending, order book/trade-strength data is missing,
the stock is halted, VI is active, the spread is too wide, or the order book is
stale. The generated signal is not an order by itself; `ExecutionEngine` and
`RiskManager` remain the final safety layer.

This score is a trading heuristic, not a profitability guarantee. Backtesting
and paper/live observation should be used before changing thresholds or weights.
