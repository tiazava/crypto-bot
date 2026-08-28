import pandas as pd
import numpy as np

def calculate_indicators(df):
    """Calcola ATR14, ADX14, RSI14, EMA200 e Donchian 20."""
    df = df.copy()

    # 1. ATR 14 e Indicatore ATR Debole (per BTC)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr'] = true_range.rolling(14).mean()

    df['atr_ma5'] = df['atr'].rolling(5).mean()
    df['atr_weak'] = df['atr'] < df['atr_ma5']
    df['atr_weak_3d'] = df['atr_weak'].shift(1).rolling(3).apply(lambda x: (x == 1).all(), raw=True).fillna(0).astype(bool)

    # 2. ADX 14
    up_move = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr_smooth = true_range.rolling(14).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(14).sum() / tr_smooth)
    minus_di = 100 * (pd.Series(minus_dm).rolling(14).sum() / tr_smooth)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    df['adx'] = dx.rolling(14).mean()

    # 3. RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 4. EMA 200
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()

    # 5. Breakout Donchian 20
    df['donchian_high'] = df['high'].shift(1).rolling(20).max()
    df['donchian_low'] = df['low'].shift(1).rolling(20).min()

    # Indicatore di rottura Donchian recente nei 3 giorni precedenti (per ETH)
    df['donchian_breakout_recent'] = (
        (df['high'].shift(1) > df['donchian_high'].shift(1)) |
        (df['low'].shift(1) < df['donchian_low'].shift(1))
    ).rolling(3).apply(lambda x: (x == 1).any(), raw=True).fillna(0).astype(bool)

    return df

def analyze_market(ohlc_data, symbol="BTC"):
    """Analizza il mercato secondo le regole esatte del Backtest v6.6."""
    if ohlc_data.empty:
        return None

    raw_df = pd.DataFrame(ohlc_data, columns=['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        raw_df[col] = raw_df[col].astype(float)

    df = calculate_indicators(raw_df)
    row = df.iloc[-1]

    if pd.isna(row['atr']) or pd.isna(row['ema200']) or pd.isna(row['donchian_high']) or pd.isna(row['adx']) or pd.isna(row['rsi']):
        return {'action': 'HOLD', 'price': row['close'], 'rsi': 0, 'atr': 0, 'leverage': 1}

    bullish = (row['close'] > row['ema200']) and (row['close'] > row['donchian_high']) and (row['adx'] > 20) and (row['rsi'] < 75)
    bearish = (row['close'] < row['ema200']) and (row['close'] < row['donchian_low']) and (row['adx'] > 20) and (row['rsi'] > 25)

    side = None
    if bullish:
        side = 'BUY'
    elif bearish:
        side = 'SELL'

    if side:
        # Determinazione Leva Adattiva
        effective_leverage = 2.0 if symbol == "BTC" else 1.5

        if symbol == "BTC" and row['atr_weak_3d']:
            effective_leverage = 3.0
            print(f"🔥 ATR weak 3d su BTC: Leva portata a 3.0x!")
        elif symbol == "ETH" and row['donchian_breakout_recent']:
            effective_leverage = 2.0
            print(f"⚡ Donchian breakout recente su ETH: Leva portata a 2.0x!")

        current_price = row['close']
        atr_val = row['atr']

        stop_loss = current_price - (3.0 * atr_val) if side == 'BUY' else current_price + (3.0 * atr_val)
        take_profit = current_price + (5.0 * atr_val) if side == 'BUY' else current_price - (5.0 * atr_val)

        return {
            'action': side,
            'price': current_price,
            'rsi': round(row['rsi'], 2),
            'adx': round(row['adx'], 2),
            'atr': round(atr_val, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'leverage': effective_leverage
        }

    return {
        'action': 'HOLD',
        'price': row['close'],
        'rsi': round(row['rsi'], 2),
        'atr': round(row['atr'], 2),
        'leverage': 1
    }
