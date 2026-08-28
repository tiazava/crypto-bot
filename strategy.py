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


# ============================================================
# INDICATORS
# ============================================================

def calculate_indicators(df):

    df = df.copy()

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # TRUE RANGE
    # --------------------------------------------------------

    previous_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]

    tr2 = abs(df["high"] - previous_close)

    tr3 = abs(df["low"] - previous_close)

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr"] = (
        true_range
        .rolling(ATR_PERIOD)
        .mean()
    )

    df["atr_ma"] = (
        df["atr"]
        .rolling(20)
        .mean()
    )


    # --------------------------------------------------------
    # ATR VOLATILITY REGIME
    # --------------------------------------------------------

    df["atr_ratio"] = (
        df["atr"] / df["atr_ma"]
    )


    # --------------------------------------------------------
    # EMA 200
    # --------------------------------------------------------

    df["ema200"] = (
        df["close"]
        .ewm(
            span=EMA_PERIOD,
            adjust=False
        )
        .mean()
    )


    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    delta = df["close"].diff()

    gain = (
        delta
        .where(delta > 0, 0)
        .rolling(RSI_PERIOD)
        .mean()
    )

    loss = (
        -delta
        .where(delta < 0, 0)
        .rolling(RSI_PERIOD)
        .mean()
    )

    rs = gain / loss.replace(0, np.nan)

    df["rsi"] = 100 - (
        100 / (1 + rs)
    )


    # --------------------------------------------------------
    # DONCHIAN
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    up_move = (
        df["high"] -
        df["high"].shift(1)
    )

    down_move = (
        df["low"].shift(1) -
        df["low"]
    )

    plus_dm = np.where(
        (up_move > down_move) &
        (up_move > 0),
        up_move,
        0.0
    )

    minus_dm = np.where(
        (down_move > up_move) &
        (down_move > 0),
        down_move,
        0.0
    )

    tr_sum = (
        true_range
        .rolling(ADX_PERIOD)
        .sum()
    )

    plus_di = (
        100 *
        pd.Series(
            plus_dm,
            index=df.index
        )
        .rolling(ADX_PERIOD)
        .sum()
        / tr_sum
    )

    minus_di = (
        100 *
        pd.Series(
            minus_dm,
            index=df.index
        )
        .rolling(ADX_PERIOD)
        .sum()
        / tr_sum
    )

    denominator = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        100 *
        abs(plus_di - minus_di)
        / denominator
    )

    df["adx"] = (
        dx
        .rolling(ADX_PERIOD)
        .mean()
    )

    return df


# ============================================================
# ANALYSE SINGOLO TIMEFRAME
# ============================================================

def analyze_timeframe(df):

    if df is None or df.empty:
        return None

    df = calculate_indicators(df)

    if len(df) < 250:
        return None

    # Ultima candela CHIUSA
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


# ============================================================
# ADAPTIVE ATR STOP
# ============================================================

def get_atr_multiplier(atr_ratio):

    if atr_ratio >= ATR_EXTREME_VOL_RATIO:
        return ATR_SL_EXTREME_VOL

    if atr_ratio >= ATR_HIGH_VOL_RATIO:
        return ATR_SL_HIGH_VOL

    return ATR_SL_NORMAL


# ============================================================
# MULTI-TIMEFRAME STRATEGY
# ============================================================

def analyze_market(
    h4_df,
    h1_df,
    m15_df,
    symbol="BTC"
):

    h4 = analyze_timeframe(h4_df)
    h1 = analyze_timeframe(h1_df)
    m15 = analyze_timeframe(m15_df)

    if not h4 or not h1 or not m15:
        return {
            "action": "HOLD",
            "reason": "Dati insufficienti"
        }


    # ========================================================
    # H4 TREND
    # ========================================================

    h4_bull = (
        h4["price"] > h4["ema200"]
    )

    h4_bear = (
        h4["price"] < h4["ema200"]
    )


    # ========================================================
    # H1 CONFIRMATION
    # ========================================================

    h1_bull = (
        h1["price"] > h1["ema200"] and
        h1["adx"] > ADX_MIN
    )

    h1_bear = (
        h1["price"] < h1["ema200"] and
        h1["adx"] > ADX_MIN
    )


    # ========================================================
    # M15 ENTRY
    # ========================================================

    long_entry = (
        m15["price"] >
        m15["donchian_high"]
        and
        m15["rsi"] <
        RSI_MAX_LONG
        and
        m15["adx"] >
        ADX_MIN
    )

    short_entry = (
        m15["price"] <
        m15["donchian_low"]
        and
        m15["rsi"] >
        RSI_MIN_SHORT
        and
        m15["adx"] >
        ADX_MIN
    )


    # ========================================================
    # SIGNAL
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
        }


    # ========================================================
    # ADAPTIVE STOP LOSS
    # ========================================================

    atr_multiplier = get_atr_multiplier(
        m15["atr_ratio"]
    )

    entry = m15["price"]

    atr = m15["atr"]

    stop_distance = atr * atr_multiplier

    if side == "BUY":

        stop_loss = entry - stop_distance

        take_profit = (
            entry +
            stop_distance *
            RISK_REWARD
        )

    else:

        stop_loss = entry + stop_distance

        take_profit = (
            entry -
            stop_distance *
            RISK_REWARD
        )


    return {
        "action": side,
        "price": round(entry, 2),
        "atr": round(atr, 2),
        "atr_ratio": round(m15["atr_ratio"], 2),
        "atr_multiplier": atr_multiplier,
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "rsi": round(m15["rsi"], 2),
        "adx": round(m15["adx"], 2),
        "h4_trend": "BULL" if h4_bull else "BEAR",
        "h1_trend": "BULL" if h1_bull else "BEAR",
        "action_reason": "H4 + H1 + M15 confermati",
    }
