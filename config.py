import os

# Credenziali API (lette dalle variabili d'ambiente sul tuo Mac/VPS)
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "LA_TUA_KRAKEN_API_KEY")
KRAKEN_SECRET_KEY = os.getenv("KRAKEN_SECRET_KEY", "LA_TUA_KRAKEN_SECRET_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "LA_TUA_ANTHROPIC_API_KEY")

# Coppie di Trading Kraken
PAIRS = {
    "BTC": "XXBTZEUR",
    "ETH": "XETHZEUR"
}

# Parametri Strategia Tecnica
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Gestione del Rischio e Leva
MAX_RISK_PER_TRADE = 0.02
LEVERAGE_MIN = 2
LEVERAGE_MAX = 4
