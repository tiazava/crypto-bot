import pandas as pd
import numpy as np

from config import (
    EMA_PERIOD,
    DONCHIAN_PERIOD,
    ATR_PERIOD,
    ADX_PERIOD,
    RSI_PERIOD,
    ADX_MIN,
    RSI_MAX_LONG,
    RSI_MIN_SHORT,
    ATR_SL_NORMAL,
    ATR_SL_HIGH_VOL,
    ATR_SL_EXTREME_VOL,
    ATR_HIGH_VOL_RATIO,
    ATR_EXTREME_VOL_RATIO,
    RISK_REWARD,
)


def calculate_indicators(df):
    """Calcola gli indicatori tecnici utilizzati dalla strategia."""

    df = df.copy()

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # ========================================================
    # TRUE RANGE / ATR
    # ========================================================

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - previous_close).abs()
    tr3 = (df["low"] - previous_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr"] = (
        true_range
        .rolling(ATR_PERIOD)
        .mean()
    )

    # Media ATR utilizzata per capire
    # il regime di volatilità corrente.
    df["atr_ma"] = (
        df["atr"]
        .rolling(20)
        .mean()
    )

    df["atr_ratio"] = (
        df["atr"] /
        df["atr_ma"]
    )

    # ========================================================
    # EMA 200
    # ========================================================

    df["ema200"] = (
        df["close"]
        .ewm(
            span=EMA_PERIOD,
            adjust=False
        )
        .mean()
    )

    # ========================================================
    # RSI
    # ========================================================

    delta = df["close"].diff()

    gain = (
        delta
        .clip(lower=0)
        .rolling(RSI_PERIOD)
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .rolling(RSI_PERIOD)
        .mean()
    )

    rs = gain / loss.replace(0, np.nan)

    df["rsi"] = (
        100 -
        (100 / (1 + rs))
    )

    # ========================================================
    # DONCHIAN CHANNEL
    # ========================================================

    # shift(1) evita di utilizzare la candela corrente
    # per determinare il breakout.
    df["donchian_high"] = (
        df["high"]
        .shift(1)
        .rolling(DONCHIAN_PERIOD)
        .max()
    )

    df["donchian_low"] = (
        df["low"]
        .shift(1)
        .rolling(DONCHIAN_PERIOD)
        .min()
    )

    # ========================================================
    # ADX
    # ========================================================

    up_move = (
        df["high"] -
        df["high"].shift(1)
    )

    down_move = (
        df["low"].shift(1) -
        df["low"]
    )

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move) &
            (up_move > 0),
            up_move,
            0.0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) &
            (down_move > 0),
            down_move,
            0.0
        ),
        index=df.index
    )

    atr_sum = (
        true_range
        .rolling(ADX_PERIOD)
        .sum()
    )

    plus_di = (
        100 *
        plus_dm
        .rolling(ADX_PERIOD)
        .sum()
        / atr_sum.replace(0, np.nan)
    )

    minus_di = (
        100 *
        minus_dm
        .rolling(ADX_PERIOD)
        .sum()
        / atr_sum.replace(0, np.nan)
    )

    di_sum = (
        plus_di +
        minus_di
    ).replace(0, np.nan)

    dx = (
        100 *
        (plus_di - minus_di).abs()
        / di_sum
    )

    df["adx"] = (
        dx
        .rolling(ADX_PERIOD)
        .mean()
    )

    return df


def analyze_timeframe(df):
    """Restituisce i dati tecnici dell'ultima candela chiusa."""

    if df is None or df.empty:
        return None

    df = calculate_indicators(df)

    # EMA200 richiede abbastanza storico.
    if len(df) < EMA_PERIOD + 30:
        return None

    row = df.iloc[-1]

    required = [
        "close",
        "ema200",
        "atr",
        "atr_ratio",
        "adx",
        "rsi",
        "donchian_high",
        "donchian_low",
    ]

    if any(pd.isna(row[x]) for x in required):
        return None

    return {
        "price": float(row["close"]),
        "ema200": float(row["ema200"]),
        "atr": float(row["atr"]),
        "atr_ratio": float(row["atr_ratio"]),
        "adx": float(row["adx"]),
        "rsi": float(row["rsi"]),
        "donchian_high": float(row["donchian_high"]),
        "donchian_low": float(row["donchian_low"]),
    }


def get_atr_multiplier(atr_ratio):
    """
    Allarga lo stop quando la volatilità aumenta.
    """

    if atr_ratio >= ATR_EXTREME_VOL_RATIO:
        return ATR_SL_EXTREME_VOL

    if atr_ratio >= ATR_HIGH_VOL_RATIO:
        return ATR_SL_HIGH_VOL

    return ATR_SL_NORMAL


def analyze_market(
    h4_df,
    h1_df,
    m15_df,
    symbol="BTC"
):
    """
    Strategia:

    H4  -> trend principale
    H1  -> conferma trend
    M15 -> trigger d'ingresso
    """

    h4 = analyze_timeframe(h4_df)
    h1 = analyze_timeframe(h1_df)
    m15 = analyze_timeframe(m15_df)

    if not h4 or not h1 or not m15:
        return {
            "action": "HOLD",
            "reason": "Dati insufficienti"
        }

    # ========================================================
    # TREND H4
    # ========================================================

    h4_bull = (
        h4["price"] >
        h4["ema200"]
    )

    h4_bear = (
        h4["price"] <
        h4["ema200"]
    )

    # ========================================================
    # CONFERMA H1
    # ========================================================

    h1_bull = (
        h1["price"] >
        h1["ema200"]
        and
        h1["adx"] >= ADX_MIN
    )

    h1_bear = (
        h1["price"] <
        h1["ema200"]
        and
        h1["adx"] >= ADX_MIN
    )

    # ========================================================
    # TRIGGER M15
    # ========================================================

    long_entry = (
        m15["price"] >
        m15["donchian_high"]
        and
        m15["rsi"] <
        RSI_MAX_LONG
        and
        m15["adx"] >=
        ADX_MIN
    )

    short_entry = (
        m15["price"] <
        m15["donchian_low"]
        and
        m15["rsi"] >
        RSI_MIN_SHORT
        and
        m15["adx"] >=
        ADX_MIN
    )

    # ========================================================
    # SEGNALE
    # ========================================================

    if h4_bull and h1_bull and long_entry:
        side = "BUY"

    elif h4_bear and h1_bear and short_entry:
        side = "SELL"

    else:
        return {
            "action": "HOLD",
            "reason": "Nessuna conferma multi-timeframe",
            "price": m15["price"],
            "h4_trend": (
                "BULL" if h4_bull else "BEAR"
            ),
            "h1_trend": (
                "BULL" if h1_bull else "BEAR"
            ),
            "m15_rsi": round(m15["rsi"], 2),
            "m15_adx": round(m15["adx"], 2),
        }

    # ========================================================
    # STOP LOSS ADATTIVO
    # ========================================================

    atr_multiplier = get_atr_multiplier(
        m15["atr_ratio"]
    )

    entry = m15["price"]
    atr = m15["atr"]

    stop_distance = (
        atr *
        atr_multiplier
    )

    # ========================================================
    # TAKE PROFIT 1:2
    # ========================================================

    if side == "BUY":

        stop_loss = (
            entry -
            stop_distance
        )

        take_profit = (
            entry +
            stop_distance *
            RISK_REWARD
        )

    else:

        stop_loss = (
            entry +
            stop_distance
        )

        take_profit = (
            entry -
            stop_distance *
            RISK_REWARD
        )

    return {
        "symbol": symbol,
        "action": side,
        "price": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "atr": round(atr, 2),
        "atr_ratio": round(
            m15["atr_ratio"],
            2
        ),
        "atr_multiplier": atr_multiplier,
        "rsi": round(
            m15["rsi"],
            2
        ),
        "adx": round(
            m15["adx"],
            2
        ),
        "h4_trend": (
            "BULL" if h4_bull else "BEAR"
        ),
        "h1_trend": (
            "BULL" if h1_bull else "BEAR"
        ),
        "reason": (
            "H4 + H1 + M15 confermati"
        ),
    }
