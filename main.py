from datetime import datetime, timezone

import config

from kraken_client import KrakenClient
from strategy import analyze_market
from anthropic_guard import AnthropicGuard


# ============================================================
# HELPERS
# ============================================================

def calculate_position_size(
    capital,
    entry,
    stop_loss,
    min_notional
):

    # Capitale massimo che possiamo perdere
    risk_amount = (
        capital *
        config.RISK_PER_TRADE
    )

    stop_distance = abs(
        entry - stop_loss
    )

    if stop_distance <= 0:

        raise ValueError(
            "Stop distance non valido"
        )

    # Quantità determinata dal rischio
    quantity_by_risk = (
        risk_amount /
        stop_distance
    )

    # Quantità minima per rispettare
    # il controvalore minimo richiesto
    quantity_by_minimum = (
        min_notional /
        entry
    )

    quantity = max(
        quantity_by_risk,
        quantity_by_minimum
    )

    notional = (
        quantity *
        entry
    )

    actual_risk = (
        quantity *
        stop_distance
    )

    # IMPORTANTISSIMO:
    # se il minimo d'ordine fa superare
    # il rischio massimo, NON TRADIAMO.
    if actual_risk > risk_amount * 1.10:

        return {
            "allowed": False,
            "reason": (
                f"Minimo ordine {min_notional:.2f} EUR "
                f"richiede rischio {actual_risk:.2f} EUR "
                f"> massimo {risk_amount:.2f} EUR"
            )
        }

    return {
        "allowed": True,
        "quantity": quantity,
        "notional": notional,
        "risk_amount": actual_risk,
    }


# ============================================================
# POSITION CHECK
# ============================================================

def has_open_position(kraken):

    positions = kraken.get_open_positions()

    return len(positions) > 0


# ============================================================
# MAIN
# ============================================================

def run():

    now = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    print(
        "\n=================================================="
    )

    print(
        f"🤖 CRYPTO BOT START - {now}"
    )

    print(
        f"MODE: {config.TRADING_MODE}"
    )

    print(
        "=================================================="
    )


    # ========================================================
    # SAFETY
    # ========================================================

    if config.TRADING_MODE == "LIVE":

        if not config.ALLOW_LIVE_TRADING:

            raise RuntimeError(
                "LIVE richiesto ma "
                "ALLOW_LIVE_TRADING != true"
            )


    # ========================================================
    # KRAKEN
    # ========================================================

    kraken = KrakenClient()

    balance = kraken.get_account_balance()

    print(
        f"💰 Saldo EUR: {balance:.2f}"
    )


    if balance <= 0:

        print(
            "🛑 Nessun saldo EUR disponibile"
        )

        return


    # ========================================================
    # POSITION LIMIT
    # ========================================================

    if has_open_position(kraken):

        print(
            "🟡 Posizione già aperta."
        )

        print(
            "Nessun nuovo trade."
        )

        return


    # ========================================================
    # ANTHROPIC
    # ========================================================

    guard = AnthropicGuard()


    # ========================================================
    # ASSETS
    # ========================================================

    for symbol, pair_info in config.PAIRS.items():

        pair = pair_info["pair"]

        min_notional = pair_info[
            "min_notional_eur"
        ]

        print(
            f"\n{'=' * 50}"
        )

        print(
            f"📊 ANALISI {symbol}"
        )

        print(
            f"{'=' * 50}"
        )


        # ====================================================
        # MARKET DATA
        # ====================================================

        try:

            h4 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES["TREND"]
            )

            h1 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES["CONFIRMATION"]
            )

            m15 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES["ENTRY"]
            )

        except Exception as e:

            print(
                f"❌ Errore dati {symbol}: {e}"
            )

            continue


        if (
            h4.empty
            or h1.empty
            or m15.empty
        ):

            print(
                "⚠️ Dati insufficienti"
            )

            continue


        # ====================================================
        # STRATEGY
        # ====================================================

        analysis = analyze_market(
            h4,
            h1,
            m15,
            symbol
        )


        print(
            f"Price: "
            f"{analysis.get('price')}"
        )

        print(
            f"Signal: "
            f"{analysis.get('action')}"
        )


        if analysis["action"] != "BUY" and \
           analysis["action"] != "SELL":

            print(
                f"⚪ HOLD: "
                f"{analysis.get('reason')}"
            )

            continue


        # ====================================================
        # SIGNAL
        # ====================================================

        side = analysis["action"]

        entry = analysis["price"]

        stop_loss = analysis["stop_loss"]

        take_profit = analysis[
            "take_profit"
        ]


        print(
            f"🚨 SIGNAL: {side}"
        )

        print(
            f"Entry: {entry:.2f}"
        )

        print(
            f"SL: {stop_loss:.2f}"
        )

        print(
            f"TP: {take_profit:.2f}"
        )

        print(
            f"ATR multiplier: "
            f"{analysis['atr_multiplier']}"
        )


        # ====================================================
        # POSITION SIZE
        # ====================================================

        sizing = calculate_position_size(
            balance,
            entry,
            stop_loss,
            min_notional
        )


        if not sizing["allowed"]:

            print(
                f"🛑 TRADE BLOCCATO: "
                f"{sizing['reason']}"
            )

            continue


        quantity = sizing["quantity"]

        notional = sizing["notional"]

        actual_risk = sizing[
            "risk_amount"
        ]


        print(
            f"Quantity: {quantity:.8f}"
        )

        print(
            f"Notional: {notional:.2f} EUR"
        )

        print(
            f"Risk: {actual_risk:.2f} EUR"
        )


        # ====================================================
        # AI GUARD
        # ====================================================

        print(
            "🧠 Controllo AI..."
        )

        decision, summary, reason = (
            guard.evaluate_news_impact(
                symbol,
                side,
                entry
            )
        )


        print(
            f"AI: {decision}"
        )

        print(
            f"News: {summary}"
        )

        print(
            f"Reason: {reason}"
        )


        if decision == "BLOCK":

            print(
                "🛑 AI ha bloccato il trade."
            )

            continue


        # ====================================================
        # PAPER
        # ====================================================

        if config.TRADING_MODE == "PAPER":

            print(
                "\n🧪 PAPER TRADE"
            )

            print(
                f"{side} {symbol}"
            )

            print(
                f"Notional: "
                f"{notional:.2f} EUR"
            )

            print(
                f"Entry: "
                f"{entry:.2f}"
            )

            print(
                f"SL: "
                f"{stop_loss:.2f}"
            )

            print(
                f"TP: "
                f"{take_profit:.2f}"
            )

            print(
                "Nessun ordine inviato a Kraken."
            )

            continue


        # ====================================================
        # LIVE
        # ====================================================

        print(
            "\n🔴 LIVE TRADING"
        )


        leverage = (
            config.LEVERAGE_BTC
            if symbol == "BTC"
            else config.LEVERAGE_ETH
        )


        try:

            result = kraken.create_market_order(
                pair=pair,
                side=side,
                volume=quantity,
                leverage=leverage
            )

            print(
                "✅ ORDINE INVIATO"
            )

            print(
                result
            )

            # ATTENZIONE:
            # SL/TP devono essere verificati
            # sull'account Kraken e sul tipo
            # di posizione/margin prima di
            # automatizzarli in LIVE.

        except Exception as e:

            print(
                f"❌ ORDINE FALLITO: {e}"
            )

            continue


    print(
        "\n=================================================="
    )

    print(
        "🏁 CRYPTO BOT END"
    )

    print(
        "=================================================="
    )


if __name__ == "__main__":

    run()
