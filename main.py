from datetime import datetime, timezone

import config

from kraken_client import KrakenClient
from strategy import analyze_market
from anthropic_guard import AnthropicGuard


# ============================================================
# POSITION SIZING
# ============================================================

def calculate_position_size(
    capital,
    allocation_pct,
    entry,
    stop_loss,
    min_notional
):
    """
    Dimensiona la posizione come percentuale del capitale.

    BTC:
    10% del capitale operativo

    ETH:
    8% del capitale operativo

    Lo stop loss viene poi utilizzato per verificare
    che il rischio monetario non superi RISK_PER_TRADE.
    """

    if capital <= 0:
        return {
            "allowed": False,
            "reason": "Capitale operativo non valido"
        }

    if entry <= 0:
        return {
            "allowed": False,
            "reason": "Prezzo di ingresso non valido"
        }

    stop_distance = abs(
        entry - stop_loss
    )

    if stop_distance <= 0:
        return {
            "allowed": False,
            "reason": "Stop loss non valido"
        }

    # ========================================================
    # CONTROVALORE POSIZIONE
    # ========================================================

    target_notional = (
        capital *
        allocation_pct
    )

    # Il controvalore stabilito deve rispettare
    # il minimo operativo dell'asset.
    if target_notional < min_notional:

        return {
            "allowed": False,
            "reason": (
                f"Allocazione prevista "
                f"{target_notional:.2f} EUR "
                f"inferiore al minimo operativo "
                f"{min_notional:.2f} EUR"
            )
        }

    # ========================================================
    # QUANTITÀ
    # ========================================================

    quantity = (
        target_notional /
        entry
    )

    # ========================================================
    # RISCHIO DELLO STOP
    # ========================================================

    actual_risk = (
        quantity *
        stop_distance
    )

    max_risk = (
        capital *
        config.RISK_PER_TRADE
    )

    if actual_risk > max_risk:

        return {
            "allowed": False,
            "reason": (
                f"Rischio SL {actual_risk:.2f} EUR "
                f"superiore al massimo "
                f"{max_risk:.2f} EUR"
            ),
            "target_notional": target_notional,
            "actual_risk": actual_risk,
            "max_risk": max_risk,
        }

    return {
        "allowed": True,
        "quantity": quantity,
        "notional": target_notional,
        "actual_risk": actual_risk,
        "max_risk": max_risk,
    }


# ============================================================
# CONTROLLO POSIZIONI
# ============================================================

def has_open_position(kraken):
    """
    Controlla eventuali posizioni margin già aperte.
    """

    positions = kraken.get_open_positions()

    return len(positions) > 0


# ============================================================
# CONTROLLO ORDINI
# ============================================================

def has_open_orders(kraken):
    """
    Evita duplicazioni se esistono ordini aperti.
    """

    orders = kraken.get_open_orders()

    return len(orders) > 0


# ============================================================
# MAIN BOT
# ============================================================

def run():

    now = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    print("\n" + "=" * 60)

    print(
        f"CRYPTO BOT START - {now}"
    )

    print(
        f"MODE: {config.TRADING_MODE}"
    )

    print("=" * 60)

    # ========================================================
    # CONTROLLO MODALITÀ
    # ========================================================

    if config.TRADING_MODE not in (
        "PAPER",
        "LIVE"
    ):

        raise RuntimeError(
            "TRADING_MODE deve essere "
            "PAPER oppure LIVE"
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

        balance = (
            kraken.get_account_balance()
        )

    except Exception as e:

        print(
            f"ERRORE KRAKEN BALANCE: {e}"
        )

        return

    print(
        f"Saldo EUR Kraken: "
        f"{balance:.2f}"
    )

    if balance <= 0:

        print(
            "Nessun saldo EUR disponibile."
        )

        return

    # ========================================================
    # CAPITALE OPERATIVO
    # ========================================================

    operating_capital = min(
        balance,
        config.CAPITAL_EUR
    )

    print(
        f"Capitale operativo bot: "
        f"{operating_capital:.2f} EUR"
    )

    print(
        f"Rischio massimo per trade: "
        f"{operating_capital * config.RISK_PER_TRADE:.2f} EUR"
    )

    # ========================================================
    # POSIZIONI / ORDINI APERTI
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
    # CICLO ASSET
    # ========================================================

    for symbol, pair_info in config.PAIRS.items():

        pair = pair_info[
            "pair"
        ]

        min_notional = pair_info[
            "min_notional_eur"
        ]

        allocation_pct = pair_info[
            "allocation_pct"
        ]

        target_notional = (
            operating_capital *
            allocation_pct
        )

        print(
            "\n" + "-" * 60
        )

        print(
            f"ANALISI {symbol}"
        )

        print(
            "-" * 60
        )

        print(
            f"Allocazione: "
            f"{allocation_pct * 100:.1f}%"
        )

        print(
            f"Controvalore previsto: "
            f"{target_notional:.2f} EUR"
        )

        # ====================================================
        # DATI H4 / H1 / M15
        # ====================================================

        try:

            h4 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES[
                    "TREND"
                ]
            )

            h1 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES[
                    "CONFIRMATION"
                ]
            )

            m15 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES[
                    "ENTRY"
                ]
            )

        except Exception as e:

            print(
                f"Errore download dati "
                f"{symbol}: {e}"
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
                f"Errore strategia "
                f"{symbol}: {e}"
            )

            continue

        print(
            f"Prezzo: "
            f"{analysis.get('price')}"
        )

        print(
            f"Segnale: "
            f"{analysis.get('action')}"
        )

        print(
            f"Motivo: "
            f"{analysis.get('reason')}"
        )

        # ====================================================
        # HOLD
        # ====================================================

        if analysis.get(
            "action"
        ) not in (
            "BUY",
            "SELL"
        ):

            print(
                "Nessun trade."
            )

            continue

        side = analysis[
            "action"
        ]

        entry = float(
            analysis[
                "price"
            ]
        )

        stop_loss = float(
            analysis[
                "stop_loss"
            ]
        )

        take_profit = float(
            analysis[
                "take_profit"
            ]
        )

        # ====================================================
        # SEGNALE
        # ====================================================

        print(
            f"SEGNALE {side} {symbol}"
        )

        print(
            f"Entry: "
            f"{entry:.2f}"
        )

        print(
            f"Stop Loss: "
            f"{stop_loss:.2f}"
        )

        print(
            f"Take Profit: "
            f"{take_profit:.2f}"
        )

        print(
            f"ATR multiplier: "
            f"{analysis['atr_multiplier']}"
        )

        print(
            f"ADX: "
            f"{analysis['adx']}"
        )

        print(
            f"RSI: "
            f"{analysis['rsi']}"
        )

        print(
            f"H4 trend: "
            f"{analysis['h4_trend']}"
        )

        print(
            f"H1 trend: "
            f"{analysis['h1_trend']}"
        )

        # ====================================================
        # POSITION SIZING
        # ====================================================

        sizing = calculate_position_size(
            capital=operating_capital,
            allocation_pct=allocation_pct,
            entry=entry,
            stop_loss=stop_loss,
            min_notional=min_notional
        )

        if not sizing[
            "allowed"
        ]:

            print(
                "TRADE BLOCCATO: "
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
            "actual_risk"
        ]

        max_risk = sizing[
            "max_risk"
        ]

        print(
            f"Quantità: "
            f"{quantity:.8f}"
        )

        print(
            f"Controvalore: "
            f"{notional:.2f} EUR"
        )

        print(
            f"Rischio SL: "
            f"{actual_risk:.2f} EUR"
        )

        print(
            f"Rischio massimo: "
            f"{max_risk:.2f} EUR"
        )

        # ====================================================
        # AI GUARD
        # ====================================================

        technical_data = {

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "take_profit":
                take_profit,

            "atr":
                analysis.get(
                    "atr"
                ),

            "atr_ratio":
                analysis.get(
                    "atr_ratio"
                ),

            "atr_multiplier":
                analysis.get(
                    "atr_multiplier"
                ),

            "rsi":
                analysis.get(
                    "rsi"
                ),

            "adx":
                analysis.get(
                    "adx"
                ),

            "h4_trend":
                analysis.get(
                    "h4_trend"
                ),

            "h1_trend":
                analysis.get(
                    "h1_trend"
                ),

            "allocation_pct":
                allocation_pct,

            "notional_eur":
                round(
                    notional,
                    2
                ),

            "risk_eur":
                round(
                    actual_risk,
                    2
                ),
        }

        print(
            "Controllo AI Guard..."
        )

        ai_result = (
            guard.evaluate_market_risk(
                asset=symbol,
                side=side,
                current_price=entry,
                technical_data=technical_data
            )
        )

        print(
            f"AI decision: "
            f"{ai_result['decision']}"
        )

        print(
            f"AI reason: "
            f"{ai_result['reason']}"
        )

        if (
            ai_result[
                "decision"
            ] != "GO"
        ):

            print(
                "Trade bloccato "
                "da AI Guard."
            )

            continue

        # ====================================================
        # PAPER MODE
        # ====================================================

        if (
            config.TRADING_MODE
            == "PAPER"
        ):

            print(
                "\nPAPER TRADE"
            )

            print(
                f"{side} {symbol}"
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
                f"Allocazione: "
                f"{allocation_pct * 100:.1f}%"
            )

            print(
                f"Controvalore: "
                f"{notional:.2f} EUR"
            )

            print(
                f"Rischio SL: "
                f"{actual_risk:.2f} EUR"
            )

            print(
                "Nessun ordine "
                "inviato a Kraken."
            )

            continue

        # ====================================================
        # LIVE MODE
        # ====================================================

        if symbol == "BTC":

            leverage = (
                config.LEVERAGE_BTC
            )

        else:

            leverage = (
                config.LEVERAGE_ETH
            )

        print(
            "\nLIVE TRADING"
        )

        print(
            f"Invio {side} "
            f"{symbol}"
        )

        try:

            result = (
                kraken.create_market_order(
                    pair=pair,
                    side=side,
                    volume=quantity,
                    leverage=leverage
                )
            )

            print(
                "ORDINE INVIATO "
                "A KRAKEN"
            )

            print(
                result
            )

        except Exception as e:

            print(
                f"ORDINE FALLITO: "
                f"{e}"
            )

            continue

        # Dopo un ordine LIVE
        # nessun altro asset viene aperto
        # nello stesso ciclo.
        break

    print(
        "\n" + "=" * 60
    )

    print(
        "CRYPTO BOT END"
    )

    print(
        "=" * 60
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    run()
