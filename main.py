from datetime import datetime, timezone

import config

from kraken_client import KrakenClient
from strategy import analyze_market
from anthropic_guard import AnthropicGuard


def calculate_position_size(
    capital,
    entry,
    stop_loss,
    min_notional
):
    """
    Calcola la size in base al rischio massimo.
    Se il minimo operativo obbliga a rischiare troppo,
    il trade viene bloccato.
    """

    risk_amount = (
        capital *
        config.RISK_PER_TRADE
    )

    stop_distance = abs(
        entry - stop_loss
    )

    if stop_distance <= 0:
        return {
            "allowed": False,
            "reason": "Stop loss non valido"
        }

    quantity_by_risk = (
        risk_amount /
        stop_distance
    )

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

    # Piccolo margine tecnico del 10%
    max_allowed_risk = (
        risk_amount * 1.10
    )

    if actual_risk > max_allowed_risk:
        return {
            "allowed": False,
            "reason": (
                f"Il minimo operativo di {min_notional:.2f} EUR "
                f"richiederebbe un rischio di {actual_risk:.2f} EUR, "
                f"superiore al limite di {risk_amount:.2f} EUR"
            )
        }

    return {
        "allowed": True,
        "quantity": quantity,
        "notional": notional,
        "risk_amount": actual_risk,
    }


def has_open_position(kraken):
    """
    Blocca nuovi ingressi se esiste già
    una posizione margin aperta.
    """

    positions = kraken.get_open_positions()

    return len(positions) > 0


def has_open_orders(kraken):
    """
    Controllo aggiuntivo:
    se ci sono ordini ancora aperti,
    evitiamo duplicazioni.
    """

    orders = kraken.get_open_orders()

    return len(orders) > 0


def run():

    now = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    print("\n" + "=" * 60)
    print(f"CRYPTO BOT START - {now}")
    print(f"MODE: {config.TRADING_MODE}")
    print("=" * 60)

    # ========================================================
    # SAFETY MODE
    # ========================================================

    if config.TRADING_MODE not in (
        "PAPER",
        "LIVE"
    ):
        raise RuntimeError(
            "TRADING_MODE deve essere PAPER oppure LIVE"
        )

    if config.TRADING_MODE == "LIVE":
        if not config.ALLOW_LIVE_TRADING:
            raise RuntimeError(
                "LIVE richiesto ma "
                "ALLOW_LIVE_TRADING non è true"
            )

    # ========================================================
    # KRAKEN
    # ========================================================

    kraken = KrakenClient()

    try:
        balance = kraken.get_account_balance()

    except Exception as e:
        print(
            f"ERRORE KRAKEN BALANCE: {e}"
        )
        return

    print(
        f"Saldo EUR disponibile: {balance:.2f}"
    )

    if balance <= 0:
        print(
            "Nessun saldo EUR disponibile."
        )
        return

    # ========================================================
    # CONTROLLO POSIZIONI / ORDINI
    # ========================================================

    try:

        if has_open_position(kraken):
            print(
                "Posizione già aperta."
            )
            print(
                "Nessun nuovo trade."
            )
            return

        if has_open_orders(kraken):
            print(
                "Ordine già aperto."
            )
            print(
                "Nessun nuovo trade."
            )
            return

    except Exception as e:

        print(
            f"ERRORE CONTROLLO POSIZIONI: {e}"
        )
        return

    # ========================================================
    # ANTHROPIC
    # ========================================================

    try:
        guard = AnthropicGuard()

    except Exception as e:
        print(
            f"ERRORE INIZIALIZZAZIONE AI: {e}"
        )
        return

    # ========================================================
    # ANALISI ASSET
    # ========================================================

    for symbol, pair_info in config.PAIRS.items():

        pair = pair_info["pair"]

        min_notional = pair_info[
            "min_notional_eur"
        ]

        print("\n" + "-" * 60)
        print(f"ANALISI {symbol}")
        print("-" * 60)

        # ====================================================
        # DATI H4 / H1 / M15
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
                f"Errore download dati {symbol}: {e}"
            )
            continue

        if (
            h4.empty
            or h1.empty
            or m15.empty
        ):
            print(
                "Dati insufficienti."
            )
            continue

        print(
            f"Candele H4: {len(h4)}"
        )
        print(
            f"Candele H1: {len(h1)}"
        )
        print(
            f"Candele M15: {len(m15)}"
        )

        # ====================================================
        # STRATEGIA
        # ====================================================

        try:

            analysis = analyze_market(
                h4,
                h1,
                m15,
                symbol
            )

        except Exception as e:

            print(
                f"Errore strategia {symbol}: {e}"
            )
            continue

        print(
            f"Prezzo: {analysis.get('price')}"
        )

        print(
            f"Segnale: {analysis.get('action')}"
        )

        print(
            f"Motivo: {analysis.get('reason')}"
        )

        # ====================================================
        # HOLD
        # ====================================================

        if analysis.get("action") not in (
            "BUY",
            "SELL"
        ):

            print(
                "Nessun trade."
            )
            continue

        side = analysis["action"]

        entry = float(
            analysis["price"]
        )

        stop_loss = float(
            analysis["stop_loss"]
        )

        take_profit = float(
            analysis["take_profit"]
        )

        # ====================================================
        # OUTPUT SEGNALE
        # ====================================================

        print(
            f"SEGNALE {side} {symbol}"
        )

        print(
            f"Entry: {entry:.2f}"
        )

        print(
            f"Stop Loss: {stop_loss:.2f}"
        )

        print(
            f"Take Profit: {take_profit:.2f}"
        )

        print(
            f"ATR multiplier: "
            f"{analysis['atr_multiplier']}"
        )

        print(
            f"ADX: {analysis['adx']}"
        )

        print(
            f"RSI: {analysis['rsi']}"
        )

        print(
            f"H4 trend: {analysis['h4_trend']}"
        )

        print(
            f"H1 trend: {analysis['h1_trend']}"
        )

        # ====================================================
        # POSITION SIZING
        # ====================================================

        sizing = calculate_position_size(
            capital=balance,
            entry=entry,
            stop_loss=stop_loss,
            min_notional=min_notional
        )

        if not sizing["allowed"]:

            print(
                f"TRADE BLOCCATO: "
                f"{sizing['reason']}"
            )
            continue

        quantity = sizing[
            "quantity"
        ]

        notional = sizing[
            "notional"
        ]

        actual_risk = sizing[
            "risk_amount"
        ]

        print(
            f"Quantità: {quantity:.8f}"
        )

        print(
            f"Controvalore: "
            f"{notional:.2f} EUR"
        )

        print(
            f"Rischio stimato: "
            f"{actual_risk:.2f} EUR"
        )

        # ====================================================
        # AI GUARD
        # ====================================================

        technical_data = {
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "atr": analysis.get("atr"),
            "atr_ratio": analysis.get(
                "atr_ratio"
            ),
            "atr_multiplier": analysis.get(
                "atr_multiplier"
            ),
            "rsi": analysis.get("rsi"),
            "adx": analysis.get("adx"),
            "h4_trend": analysis.get(
                "h4_trend"
            ),
            "h1_trend": analysis.get(
                "h1_trend"
            ),
            "notional_eur": round(
                notional,
                2
            ),
            "risk_eur": round(
                actual_risk,
                2
            ),
        }

        print(
            "Controllo AI Guard..."
        )

        ai_result = guard.evaluate_market_risk(
            asset=symbol,
            side=side,
            current_price=entry,
            technical_data=technical_data
        )

        print(
            f"AI decision: "
            f"{ai_result['decision']}"
        )

        print(
            f"AI reason: "
            f"{ai_result['reason']}"
        )

        if ai_result["decision"] != "GO":

            print(
                "Trade bloccato da AI Guard."
            )
            continue

        # ====================================================
        # PAPER MODE
        # ====================================================

        if config.TRADING_MODE == "PAPER":

            print("\nPAPER TRADE")
            print(
                f"{side} {symbol}"
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
                f"Controvalore: "
                f"{notional:.2f} EUR"
            )

            print(
                f"Rischio: "
                f"{actual_risk:.2f} EUR"
            )

            print(
                "Nessun ordine inviato a Kraken."
            )

            continue

        # ====================================================
        # LIVE MODE
        # ====================================================

        if symbol == "BTC":
            leverage = config.LEVERAGE_BTC

        else:
            leverage = config.LEVERAGE_ETH

        print(
            "\nLIVE TRADING"
        )

        print(
            f"Invio {side} {symbol}"
        )

        try:

            result = kraken.create_market_order(
                pair=pair,
                side=side,
                volume=quantity,
                leverage=leverage
            )

            print(
                "ORDINE INVIATO A KRAKEN"
            )

            print(
                result
            )

            # IMPORTANTE:
            # non automatizziamo ancora SL/TP reali.
            # Prima verifichiamo esattamente il comportamento
            # dell'account Kraken margin.

        except Exception as e:

            print(
                f"ORDINE FALLITO: {e}"
            )

            continue

        # Sicurezza:
        # dopo un ordine LIVE usciamo dal ciclo
        # per evitare più ingressi nello stesso run.
        break

    print("\n" + "=" * 60)
    print("CRYPTO BOT END")
    print("=" * 60)


if __name__ == "__main__":
    run()
