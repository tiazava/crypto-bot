from datetime import datetime, timezone

import config

from kraken_client import KrakenClient
from strategy import analyze_market
from trade_state import TradeState
from telegram_notifier import send_telegram_message


# ============================================================
# ANALISI SINGOLO ASSET
# ============================================================

def get_asset_status(
    kraken,
    symbol,
    pair,
):
    try:
        h4 = kraken.get_ohlc(
            pair,
            config.TIMEFRAMES["TREND"],
        )

        h1 = kraken.get_ohlc(
            pair,
            config.TIMEFRAMES["CONFIRMATION"],
        )

        m15 = kraken.get_ohlc(
            pair,
            config.TIMEFRAMES["ENTRY"],
        )

        if (
            h4.empty
            or h1.empty
            or m15.empty
        ):
            return {
                "symbol": symbol,
                "status": "ERRORE",
                "price": None,
                "reason": "Dati OHLC insufficienti",
            }

        analysis = analyze_market(
            h4,
            h1,
            m15,
            symbol,
        )

        return {
            "symbol": symbol,
            "status": analysis.get(
                "action",
                "HOLD"
            ),
            "price": analysis.get(
                "price"
            ),
            "reason": analysis.get(
                "reason",
                "Nessun motivo disponibile"
            ),
        }

    except Exception as e:

        return {
            "symbol": symbol,
            "status": "ERRORE",
            "price": None,
            "reason": str(e),
        }


# ============================================================
# FORMATTA ASSET
# ============================================================

def format_asset_status(data):

    symbol = data[
        "symbol"
    ]

    status = data[
        "status"
    ]

    price = data.get(
        "price"
    )

    reason = data.get(
        "reason",
        ""
    )

    if status == "BUY":
        icon = "🟢"

    elif status == "SELL":
        icon = "🔴"

    elif status == "HOLD":
        icon = "⚪"

    else:
        icon = "⚠️"

    if price is None:

        price_text = "N/D"

    else:

        try:
            price_text = (
                f"{float(price):,.2f} €"
            )

        except Exception:
            price_text = str(
                price
            )

    return (
        f"{icon} <b>{symbol}</b>\n"
        f"Segnale: <b>{status}</b>\n"
        f"Prezzo: {price_text}\n"
        f"Motivo: {reason}"
    )


# ============================================================
# MAIN REPORT
# ============================================================

def run():

    print(
        "=" * 60
    )

    print(
        "DAILY REPORT START"
    )

    print(
        "=" * 60
    )

    kraken = KrakenClient()
    state = TradeState()

    # ========================================================
    # SALDO
    # ========================================================

    try:

        balance = (
            kraken.get_account_balance()
        )

    except Exception as e:

        print(
            f"Errore saldo Kraken: {e}"
        )

        send_telegram_message(
            "⚠️ <b>REPORT CRYPTO BOT</b>\n\n"
            "Impossibile leggere il saldo Kraken.\n"
            f"Errore: {e}"
        )

        return

    operating_capital = min(
        balance,
        config.CAPITAL_EUR
    )

    # ========================================================
    # RISK STATE
    # ========================================================

    try:

        risk = (
            state.get_risk_state()
        )

        daily_pnl = float(
            risk.get(
                "daily_pnl_eur",
                0.0
            )
        )

        consecutive_losses = int(
            risk.get(
                "consecutive_losses",
                0
            )
        )

        trading_blocked = bool(
            risk.get(
                "trading_blocked",
                False
            )
        )

        block_reason = risk.get(
            "block_reason"
        )

    except Exception as e:

        daily_pnl = 0.0
        consecutive_losses = 0
        trading_blocked = True
        block_reason = (
            f"Errore Firestore: {e}"
        )

    # ========================================================
    # TRADE ATTIVO
    # ========================================================

    try:

        active_trade = (
            state.get_active_trade()
        )

    except Exception:

        active_trade = None

    if active_trade:

        trade_text = (
            f"📌 <b>TRADE ATTIVO</b>\n"
            f"Asset: {active_trade.get('symbol')}\n"
            f"Lato: {active_trade.get('side')}\n"
            f"Stato: {active_trade.get('status')}"
        )

    else:

        trade_text = (
            "📌 <b>TRADE ATTIVO</b>\n"
            "Nessuna posizione gestita dal bot."
        )

    # ========================================================
    # ANALISI BTC / ETH
    # ========================================================

    btc_info = get_asset_status(
        kraken=kraken,
        symbol="BTC",
        pair=config.PAIRS["BTC"]["pair"],
    )

    eth_info = get_asset_status(
        kraken=kraken,
        symbol="ETH",
        pair=config.PAIRS["ETH"]["pair"],
    )

    btc_text = format_asset_status(
        btc_info
    )

    eth_text = format_asset_status(
        eth_info
    )

    # ========================================================
    # STATO TRADING
    # ========================================================

    if trading_blocked:

        trading_status = (
            "🛑 BLOCCATO"
        )

        trading_reason = (
            block_reason
            or "Limite di rischio raggiunto"
        )

    else:

        trading_status = (
            "✅ OPERATIVO"
        )

        trading_reason = (
            "Limiti di rischio OK"
        )

    # ========================================================
    # ORARIO
    # ========================================================

    now = datetime.now(
        timezone.utc
    ).strftime(
        "%d/%m/%Y %H:%M UTC"
    )

    # ========================================================
    # MESSAGGIO
    # ========================================================

    message = (
        "📊 <b>REPORT GIORNALIERO CRYPTO BOT</b>\n\n"

        f"🕒 {now}\n"
        f"Modalità: <b>{config.TRADING_MODE}</b>\n\n"

        "💰 <b>CAPITALE</b>\n"
        f"Saldo Kraken: {balance:.2f} €\n"
        f"Capitale operativo: {operating_capital:.2f} €\n"
        f"Rischio max/trade: "
        f"{operating_capital * config.RISK_PER_TRADE:.2f} €\n\n"

        "🛡 <b>RISK CONTROL</b>\n"
        f"P&L giornaliero: {daily_pnl:.2f} €\n"
        f"Limite giornaliero: "
        f"-{operating_capital * config.MAX_DAILY_LOSS:.2f} €\n"
        f"Perdite consecutive: "
        f"{consecutive_losses}/"
        f"{config.MAX_CONSECUTIVE_LOSSES}\n"
        f"Trading: <b>{trading_status}</b>\n"
        f"Motivo: {trading_reason}\n\n"

        f"{trade_text}\n\n"

        "🔎 <b>CONTROLLO MERCATO</b>\n\n"

        f"{btc_text}\n\n"

        f"{eth_text}\n\n"

        "✅ Controllo giornaliero completato."
    )

    # ========================================================
    # TELEGRAM
    # ========================================================

    success = (
        send_telegram_message(
            message
        )
    )

    if success:

        print(
            "Report Telegram inviato."
        )

    else:

        print(
            "Invio report Telegram fallito."
        )

    print(
        "=" * 60
    )

    print(
        "DAILY REPORT END"
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":
    run()
