# PulseTrade Short-Term Score

The strategy score is a -100 to 100 weighted composite. It is tuned for short
term trading over intraday to one or two trading days, not for long-term
investment selection.

Current scoring components:

- Volume spike: current 1-minute volume compared with recent average volume.
- Price location: distance from nearby support and resistance.
- Trend structure: whether recent highs and lows are rising or falling.
- Breakout confirmation: close above recent high with volume confirmation.
- Pullback quality: lighter volume on pullback and renewed volume on rebound.
- Moving average alignment: 5/20/60 average alignment and slope.
- VWAP: current price position versus intraday VWAP.
- Candle quality: body strength, upper wick pressure, and lower wick support.
- Momentum indicators: RSI direction and MACD histogram direction.
- Risk/reward: distance to support as risk versus resistance as reward.
- Market regime: KOSPI/KOSDAQ proxy trend using `069500` and `229200`.

Order book and trade strength remain part of realtime readiness and risk checks,
but they are no longer the main score drivers. LIVE automation is still blocked;
LIVE mode runs this as signal-only unless a separate live automation release is
made.

Decision thresholds:

- `BUY`: score >= 70 and risk filter passes.
- `SELL`: held position score <= -60.
- `EXIT`: held position score <= -80.
- `WAIT`: every other state.

This is a rule-based scoring model, not a guarantee. Scores should be reviewed
against actual charts before thresholds are used for automated execution.
