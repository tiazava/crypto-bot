import os

# ============================================================
# MODALITÀ OPERATIVA
# ============================================================

TRADING_MODE = os.getenv(
    "TRADING_MODE",
    "PAPER"
).upper()

ALLOW_LIVE_TRADING = (
    os.getenv(
        "ALLOW_LIVE_TRADING",
        "false"
    ).lower() == "true"
)


# ============================================================
# API
# ============================================================

KRAKEN_API_KEY = os.getenv(
    "KRAKEN_API_KEY",
    ""
).strip()

KRAKEN_SECRET_KEY = os.getenv(
    "KRAKEN_SECRET_KEY",
    ""
).strip()

ANTHROPIC_API_KEY = os.getenv(
    "ANTHROPIC_API_KEY",
    ""
).strip()

ANTHROPIC_MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    "claude-sonnet-5"
).strip()


# ============================================================
# CAPITALE OPERATIVO
# ============================================================

# Il bot userà al massimo questo capitale
# anche se sul conto Kraken è presente più denaro.
CAPITAL_EUR = 150.0


# ============================================================
# ASSET / ALLOCAZIONE
# ============================================================

PAIRS = {

    "BTC": {
        "pair": "XXBTZEUR",

        # 10% del capitale operativo
        # 150 EUR -> 15 EUR
        "allocation_pct": 0.10,

        # Controvalore minimo consentito
        "min_notional_eur": 15.0,
    },

    "ETH": {
        "pair": "XETHZEUR",

        # 8% del capitale operativo
        # 150 EUR -> 12 EUR
        "allocation_pct": 0.08,

        # Controvalore minimo consentito
        "min_notional_eur": 10.0,
    },
}


# ============================================================
# TIMEFRAME
# ============================================================

TIMEFRAMES = {

    # Trend principale
    "TREND": 240,          # H4

    # Conferma trend
    "CONFIRMATION": 60,    # H1

    # Trigger ingresso
    "ENTRY": 15,           # M15
}


# ============================================================
# PARAMETRI STRATEGIA
# ============================================================

EMA_PERIOD = 200

DONCHIAN_PERIOD = 20

ATR_PERIOD = 14

ADX_PERIOD = 14

RSI_PERIOD = 14


# ============================================================
# FILTRI DI INGRESSO
# ============================================================

ADX_MIN = 20

RSI_MAX_LONG = 75

RSI_MIN_SHORT = 25


# ============================================================
# STOP LOSS ADATTIVO
# ============================================================

# Volatilità normale
ATR_SL_NORMAL = 2.5

# Volatilità elevata
ATR_SL_HIGH_VOL = 3.0

# Volatilità estrema
ATR_SL_EXTREME_VOL = 3.5


# Rapporto ATR corrente / ATR medio

ATR_HIGH_VOL_RATIO = 1.30

ATR_EXTREME_VOL_RATIO = 1.70


# ============================================================
# TAKE PROFIT
# ============================================================

# Rapporto rischio / rendimento
# R:R = 1:2
RISK_REWARD = 2.0


# ============================================================
# RISK MANAGEMENT
# ============================================================

# Perdita teorica massima consigliata
# per singola operazione.
RISK_PER_TRADE = 0.005     # 0.5%

# Perdita giornaliera massima
MAX_DAILY_LOSS = 0.02      # 2%

# Massimo numero di posizioni contemporanee
MAX_OPEN_POSITIONS = 1

# Stop dopo 3 perdite consecutive
MAX_CONSECUTIVE_LOSSES = 3


# ============================================================
# LEVA
# ============================================================

# La leva verrà usata solo dopo verifica
# della compatibilità dell'account Kraken.

LEVERAGE_BTC = 2.0

LEVERAGE_ETH = 2.0


# ============================================================
# ESECUZIONE
# ============================================================

REQUEST_TIMEOUT = 20

MIN_SIGNAL_DISTANCE = 0.001


# ============================================================
# LOGGING
# ============================================================

BOT_NAME = "crypto-bot"
