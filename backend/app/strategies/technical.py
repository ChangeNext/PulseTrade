from decimal import Decimal

from app.strategies.base import PriceBar


ZERO = Decimal("0")
HUNDRED = Decimal("100")


def clamp_score(value: Decimal) -> Decimal:
    return max(Decimal("-100"), min(Decimal("100"), value))


def pct_change(current: Decimal, previous: Decimal) -> Decimal:
    if previous <= 0:
        return ZERO
    return (current - previous) / previous * HUNDRED


def average(values: tuple[Decimal, ...] | list[Decimal]) -> Decimal:
    if not values:
        return ZERO
    return sum(values) / Decimal(len(values))


def sma(values: tuple[Decimal, ...], window: int) -> Decimal:
    if len(values) < window:
        return ZERO
    return average(values[-window:])


def ema(values: tuple[Decimal, ...], window: int) -> tuple[Decimal, ...]:
    if len(values) < window:
        return ()
    multiplier = Decimal("2") / Decimal(window + 1)
    current = average(values[:window])
    result = [current]
    for value in values[window:]:
        current = (value - current) * multiplier + current
        result.append(current)
    return tuple(result)


def rsi(values: tuple[Decimal, ...], window: int = 14) -> Decimal | None:
    if len(values) < window + 1:
        return None
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in zip(values[-window - 1 : -1], values[-window:]):
        change = current - previous
        if change >= 0:
            gains.append(change)
            losses.append(ZERO)
        else:
            gains.append(ZERO)
            losses.append(abs(change))
    average_gain = average(gains)
    average_loss = average(losses)
    if average_loss == 0:
        return HUNDRED
    relative_strength = average_gain / average_loss
    return HUNDRED - (HUNDRED / (Decimal("1") + relative_strength))


def macd_histogram(values: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    if len(values) < 35:
        return ()
    ema12 = ema(values, 12)
    ema26 = ema(values, 26)
    if not ema12 or not ema26:
        return ()
    offset = len(ema12) - len(ema26)
    macd_values = tuple(short - long for short, long in zip(ema12[offset:], ema26))
    signal = ema(macd_values, 9)
    if not signal:
        return ()
    macd_offset = len(macd_values) - len(signal)
    return tuple(macd - sig for macd, sig in zip(macd_values[macd_offset:], signal))


def volume_average(bars: tuple[PriceBar, ...], window: int) -> Decimal:
    if len(bars) < window:
        return ZERO
    return Decimal(sum(bar.volume for bar in bars[-window:])) / Decimal(window)


def support_resistance(
    bars: tuple[PriceBar, ...],
    price: Decimal,
    *,
    lookback: int = 80,
) -> tuple[Decimal | None, Decimal | None]:
    candidates = bars[-lookback:]
    supports = [bar.low for bar in candidates if ZERO < bar.low < price]
    resistances = [bar.high for bar in candidates if bar.high > price]
    support = max(supports) if supports else None
    resistance = min(resistances) if resistances else None
    return support, resistance


def merged_bars(*groups: tuple[PriceBar, ...]) -> tuple[PriceBar, ...]:
    bars: list[PriceBar] = []
    for group in groups:
        bars.extend(group)
    return tuple(bars)
