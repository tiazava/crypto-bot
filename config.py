import os


# ============================================================
# MODALITÀ OPERATIVA
# ============================================================

# PAPER = simula gli ordini
# LIVE  = invia realmente gli ordini a Kraken
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()

ALLOW_LIVE_TRADING = (
    os.getenv("ALLOW_LIVE_TRADING", "false").lower() == "true"
)


# ============================================================
# API
# ============================================================

KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "").strip()
KRAKEN_SECRET_KEY = os.getenv("KRAKEN_SECRET_KEY", "").strip()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

ANTHROPIC_MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    "claude-3-5-sonnet-20241022"
)


# ============================================================
# TRADING PAIRS
# ============================================================

PAIRS = {
    "BTC": {
        "pair": "XXBTZEUR",
        "min_notional_eur": 15.0,
    },

    "ETH": {
        "pair": "XETHZEUR",
        "min_notional_eur": 10.0,
    },
}


# ============================================================
# TIMEFRAME
# ============================================================

TIMEFRAMES = {
    "TREND": 240,       # H4
    "CONFIRMATION": 60, # H1
    "ENTRY": 15,        # M15
}


# ============================================================
# STRATEGY
# ============================================================

EMA_PERIOD = 200

DONCHIAN_PERIOD = 20

ATR_PERIOD = 14

ADX_PERIOD = 14

RSI_PERIOD = 14


# ============================================================
# ENTRY FILTERS
# ============================================================

ADX_MIN = 20

RSI_MAX_LONG = 75

RSI_MIN_SHORT = 25


# ============================================================
# RISK MANAGEMENT
# ============================================================

CAPITAL_EUR = 150.0

RISK_PER_TRADE = 0.005       # 0.5%

MAX_DAILY_LOSS = 0.02        # 2%

MAX_OPEN_POSITIONS = 1

MAX_CONSECUTIVE_LOSSES = 3


# ============================================================
# ADAPTIVE STOP LOSS
# ============================================================

ATR_SL_NORMAL = 2.5

ATR_SL_HIGH_VOL = 3.0

ATR_SL_EXTREME_VOL = 3.5

ATR_HIGH_VOL_RATIO = 1.30

ATR_EXTREME_VOL_RATIO = 1.70


# ============================================================
# TAKE PROFIT
# ============================================================

RISK_REWARD = 2.0


# ============================================================
# LEVERAGE
# ============================================================

# ATTENZIONE:
# la disponibilità effettiva della margin/leverage dipende
# dalla coppia e dal tipo di conto Kraken.

LEVERAGE_BTC = 2.0
LEVERAGE_ETH = 1.5


# ============================================================
# EXECUTION
# ============================================================

REQUEST_TIMEOUT = 20

# Non aprire un nuovo trade se il prezzo è troppo vicino
# al segnale precedente.
MIN_SIGNAL_DISTANCE = 0.001


# ============================================================
# LOGGING
# ============================================================

BOT_NAME = "crypto-bot"
