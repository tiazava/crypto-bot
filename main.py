import time
from datetime import datetime, timezone

import config

from kraken_client import KrakenClient
from strategy import analyze_market
from anthropic_guard import AnthropicGuard
from trade_state import TradeState

from telegram_notifier import (
    notify_trade_open,
    notify_take_profit,
    notify_stop_loss,
    send_telegram_message,
)


# ============================================================
# POSITION SIZING
# ============================================================

def calculate_position_size(
    capital,
    allocation_pct,
    entry,
    stop_loss,
    min_notional,
):
    if capital <= 0:
        return {
            "allowed": False,
            "reason": "Capitale operativo non valido",
        }

    if entry <= 0:
        return {
            "allowed": False,
            "reason": "Prezzo di ingresso non valido",
        }

    stop_distance = abs(
        entry - stop_loss
    )

    if stop_distance <= 0:
        return {
            "allowed": False,
            "reason": "Stop loss non valido",
        }

    target_notional = (
        capital * allocation_pct
    )

    if target_notional < min_notional:
        return {
            "allowed": False,
            "reason": (
                f"Allocazione prevista "
                f"{target_notional:.2f} EUR "
                f"inferiore al minimo operativo "
                f"{min_notional:.2f} EUR"
            ),
        }

    quantity = (
        target_notional / entry
    )

    actual_risk = (
        quantity * stop_distance
    )

    max_risk = (
        capital
        * config.RISK_PER_TRADE
    )

    if actual_risk > max_risk:
        return {
            "allowed": False,
            "reason": (
                f"Rischio SL "
                f"{actual_risk:.2f} EUR "
                f"superiore al massimo "
                f"{max_risk:.2f} EUR"
            ),
        }

    return {
        "allowed": True,
        "quantity": quantity,
        "notional": target_notional,
        "actual_risk": actual_risk,
        "max_risk": max_risk,
    }


# ============================================================
# TXID
# ============================================================

def extract_txid(result):

    txids = result.get(
        "txid",
        []
    )

    if not txids:
        return None

    return txids[0]


# ============================================================
# INFO ORDINE
# ============================================================

def order_is_filled(order):

    if not order:
        return False

    status = str(
        order.get(
            "status",
            ""
        )
    ).lower()

    try:
        vol_exec = float(
            order.get(
                "vol_exec",
                0
            )
        )
    except Exception:
        vol_exec = 0

    return (
        status == "closed"
        and vol_exec > 0
    )


def get_fill_price(
    order,
    fallback
):

    try:
        price = float(
            order.get(
                "price",
                0
            )
        )

        if price > 0:
            return price

    except Exception:
        pass

    return float(
        fallback
    )


def get_filled_volume(
    order,
    fallback
):

    try:
        volume = float(
            order.get(
                "vol_exec",
                0
            )
        )

        if volume > 0:
            return volume

    except Exception:
        pass

    return float(
        fallback
    )


# ============================================================
# PNL
# ============================================================

def calculate_pnl(
    side,
    entry,
    exit_price,
    volume,
):

    if side.upper() == "BUY":

        pnl = (
            exit_price - entry
        ) * volume

    else:

        pnl = (
            entry - exit_price
        ) * volume

    return float(
        pnl
    )


# ============================================================
# CANCELLA ORDINE SENZA CRASH
# ============================================================

def safe_cancel(
    kraken,
    txid
):

    if not txid:
        return

    try:

        kraken.cancel_order(
            txid
        )

        print(
            f"Ordine {txid} cancellato."
        )

    except Exception as e:

        # Se è già chiuso/cancellato
        # non blocchiamo il bot.
        print(
            f"Impossibile cancellare "
            f"{txid}: {e}"
        )


# ============================================================
# MONITOR TRADE ESISTENTE
# ============================================================

def monitor_active_trade(
    kraken,
    state,
    trade,
):

    print(
        "\nTRADE ATTIVO TROVATO"
    )

    print(
        f"Asset: "
        f"{trade.get('symbol')}"
    )

    print(
        f"Stato: "
        f"{trade.get('status')}"
    )

    status = trade.get(
        "status"
    )

    # --------------------------------------------------------
    # ENTRY NON ANCORA CONFERMATA
    # --------------------------------------------------------

    if status == "ENTRY_PENDING":

        entry_txid = trade.get(
            "entry_txid"
        )

        if not entry_txid:

            print(
                "Entry TXID non ancora presente."
            )

            return True

        order = (
            kraken.get_order_info(
                entry_txid
            )
        )

        if not order_is_filled(
            order
        ):

            print(
                "Entry non ancora eseguita."
            )

            return True

        fill_price = (
            get_fill_price(
                order,
                trade[
                    "requested_entry_price"
                ]
            )
        )

        filled_volume = (
            get_filled_volume(
                order,
                trade[
                    "requested_volume"
                ]
            )
        )

        state.mark_entry_filled(
            fill_price=fill_price,
            filled_volume=filled_volume,
        )

        trade = (
            state.get_active_trade()
        )

        status = "ENTRY_FILLED"

    # --------------------------------------------------------
    # ENTRY ESEGUITA MA NON PROTETTA
    # --------------------------------------------------------

    if status in {
        "ENTRY_FILLED",
        "PROTECTION_PENDING",
    }:

        pair = trade["pair"]
        side = trade["side"]

        volume = trade.get(
            "entry_filled_volume"
        )

        if not volume:
            volume = trade[
                "requested_volume"
            ]

        leverage = trade[
            "leverage"
        ]

        stop_loss = trade[
            "stop_loss"
        ]

        take_profit = trade[
            "take_profit"
        ]

        state.mark_protection_pending()

        stop_txid = trade.get(
            "stop_txid"
        )

        tp_txid = trade.get(
            "take_profit_txid"
        )

        try:

            # STOP LOSS
            if not stop_txid:

                stop_result = (
                    kraken.create_stop_loss_order(
                        pair=pair,
                        entry_side=side,
                        volume=volume,
                        stop_price=stop_loss,
                        leverage=leverage,
                        validate=False,
                        reduce_only=True,
                    )
                )

                stop_txid = extract_txid(
                    stop_result
                )

                if not stop_txid:
                    raise RuntimeError(
                        "Kraken non ha restituito "
                        "TXID Stop Loss"
                    )

                state.set_stop_order(
                    stop_txid
                )

            # TAKE PROFIT
            if not tp_txid:

                tp_result = (
                    kraken.create_take_profit_order(
                        pair=pair,
                        entry_side=side,
                        volume=volume,
                        take_profit_price=
                        take_profit,
                        leverage=leverage,
                        validate=False,
                        reduce_only=True,
                    )
                )

                tp_txid = extract_txid(
                    tp_result
                )

                if not tp_txid:
                    raise RuntimeError(
                        "Kraken non ha restituito "
                        "TXID Take Profit"
                    )

                state.set_take_profit_order(
                    tp_txid
                )

            state.mark_protected()

            trade = (
                state.get_active_trade()
            )

            print(
                "Posizione protetta "
                "con SL + TP."
            )

            # Telegram apertura
            if not trade.get(
                "telegram_open_sent"
            ):

                entry_price = (
                    trade.get(
                        "entry_fill_price"
                    )
                    or trade[
                        "requested_entry_price"
                    ]
                )

                notional = (
                    float(volume)
                    * float(entry_price)
                )

                risk = (
                    abs(
                        float(entry_price)
                        - float(stop_loss)
                    )
                    * float(volume)
                )

                notify_trade_open(
                    symbol=trade["symbol"],
                    side=side,
                    entry=float(entry_price),
                    stop_loss=float(
                        stop_loss
                    ),
                    take_profit=float(
                        take_profit
                    ),
                    notional=float(
                        notional
                    ),
                    risk=float(
                        risk
                    ),
                )

                state.mark_telegram_open_sent()

            return True

        except Exception as protection_error:

            print(
                "ERRORE PROTEZIONE: "
                f"{protection_error}"
            )

            # Cancella eventuali protezioni
            # create prima dell'errore.
            if stop_txid:
                safe_cancel(
                    kraken,
                    stop_txid
                )

            if tp_txid:
                safe_cancel(
                    kraken,
                    tp_txid
                )

            send_telegram_message(
                "🚨 ERRORE PROTEZIONE TRADE\n\n"
                f"{trade['symbol']} {side}\n"
                "Tentativo di chiusura "
                "di emergenza in corso."
            )

            try:

                emergency_result = (
                    kraken.close_position_market(
                        pair=pair,
                        entry_side=side,
                        volume=volume,
                        leverage=leverage,
                        validate=False,
                    )
                )

                emergency_txid = extract_txid(
                    emergency_result
                )

                print(
                    "Chiusura emergenza inviata: "
                    f"{emergency_txid}"
                )

                state.close_trade(
                    close_reason=
                    "EMERGENCY_PROTECTION_FAILURE"
                )

                send_telegram_message(
                    "🚨 POSIZIONE CHIUSA "
                    "IN EMERGENZA\n\n"
                    f"Asset: {trade['symbol']}\n"
                    "Motivo: impossibile creare "
                    "correttamente SL/TP."
                )

            except Exception as emergency_error:

                print(
                    "ERRORE GRAVE: "
                    "chiusura emergenza fallita: "
                    f"{emergency_error}"
                )

                # NON marchiamo CLOSED.
                # In questo modo al prossimo
                # avvio il bot riproverà.
                send_telegram_message(
                    "🚨🚨 ATTENZIONE CRITICA\n\n"
                    f"{trade['symbol']} "
                    "potrebbe essere SENZA "
                    "protezione.\n"
                    "Chiusura automatica "
                    "di emergenza fallita.\n\n"
                    "Controllare Kraken "
                    "immediatamente."
                )

            return True

    # --------------------------------------------------------
    # TRADE PROTETTO
    # --------------------------------------------------------

    if status == "PROTECTED":

        stop_txid = trade.get(
            "stop_txid"
        )

        tp_txid = trade.get(
            "take_profit_txid"
        )

        stop_order = (
            kraken.get_order_info(
                stop_txid
            )
            if stop_txid
            else {}
        )

        tp_order = (
            kraken.get_order_info(
                tp_txid
            )
            if tp_txid
            else {}
        )

        stop_filled = (
            order_is_filled(
                stop_order
            )
        )

        tp_filled = (
            order_is_filled(
                tp_order
            )
        )

        # TAKE PROFIT
        if tp_filled:

            print(
                "TAKE PROFIT ESEGUITO"
            )

            state.mark_exit_pending(
                "TAKE_PROFIT"
            )

            safe_cancel(
                kraken,
                stop_txid
            )

            entry_price = float(
                trade.get(
                    "entry_fill_price"
                )
                or trade[
                    "requested_entry_price"
                ]
            )

            volume = float(
                trade.get(
                    "entry_filled_volume"
                )
                or trade[
                    "requested_volume"
                ]
            )

            exit_price = (
                get_fill_price(
                    tp_order,
                    trade[
                        "take_profit"
                    ]
                )
            )

            pnl = calculate_pnl(
                side=trade["side"],
                entry=entry_price,
                exit_price=exit_price,
                volume=volume,
            )

            if not trade.get(
                "telegram_close_sent"
            ):

                notify_take_profit(
                    symbol=trade[
                        "symbol"
                    ],
                    side=trade[
                        "side"
                    ],
                    entry=entry_price,
                    exit_price=exit_price,
                    profit=pnl,
                )

                state.mark_telegram_close_sent()

            state.close_trade(
                close_reason=
                "TAKE_PROFIT",
                exit_price=exit_price,
                pnl_eur=pnl,
            )

            return True

        # STOP LOSS
        if stop_filled:

            print(
                "STOP LOSS ESEGUITO"
            )

            state.mark_exit_pending(
                "STOP_LOSS"
            )

            safe_cancel(
                kraken,
                tp_txid
            )

            entry_price = float(
                trade.get(
                    "entry_fill_price"
                )
                or trade[
                    "requested_entry_price"
                ]
            )

            volume = float(
                trade.get(
                    "entry_filled_volume"
                )
                or trade[
                    "requested_volume"
                ]
            )

            exit_price = (
                get_fill_price(
                    stop_order,
                    trade[
                        "stop_loss"
                    ]
                )
            )

            pnl = calculate_pnl(
                side=trade["side"],
                entry=entry_price,
                exit_price=exit_price,
                volume=volume,
            )

            if not trade.get(
                "telegram_close_sent"
            ):

                notify_stop_loss(
                    symbol=trade[
                        "symbol"
                    ],
                    side=trade[
                        "side"
                    ],
                    entry=entry_price,
                    exit_price=exit_price,
                    loss=pnl,
                )

                state.mark_telegram_close_sent()

            state.close_trade(
                close_reason=
                "STOP_LOSS",
                exit_price=exit_price,
                pnl_eur=pnl,
            )

            return True

        print(
            "Trade ancora aperto e protetto."
        )

        return True

    return True

# ============================================================
# CONTROLLO LIMITI DI RISCHIO
# ============================================================

def check_risk_limits(
    state,
    operating_capital,
):

    risk = state.get_risk_state()

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

    already_blocked = bool(
        risk.get(
            "trading_blocked",
            False
        )
    )

    block_reason = risk.get(
        "block_reason"
    )

    max_daily_loss_eur = (
        operating_capital
        * config.MAX_DAILY_LOSS
    )

    print("\nRISK CONTROL")

    print(
        f"P&L giornaliero: "
        f"{daily_pnl:.2f} EUR"
    )

    print(
        f"Perdita giornaliera massima: "
        f"{max_daily_loss_eur:.2f} EUR"
    )

    print(
        f"Perdite consecutive: "
        f"{consecutive_losses}/"
        f"{config.MAX_CONSECUTIVE_LOSSES}"
    )

    # --------------------------------------------------------
    # PERDITA GIORNALIERA
    # --------------------------------------------------------

    if daily_pnl <= -max_daily_loss_eur:

        reason = (
            "Limite perdita giornaliera "
            f"raggiunto: {daily_pnl:.2f} EUR"
        )

        if not already_blocked:

            state.block_trading(
                reason
            )

            send_telegram_message(
                "🛑 CRYPTO BOT BLOCCATO\n\n"
                "Limite perdita giornaliera "
                "raggiunto.\n"
                f"P&L oggi: {daily_pnl:.2f} EUR\n"
                f"Limite: -{max_daily_loss_eur:.2f} EUR\n\n"
                "Nessun nuovo trade fino "
                "al prossimo giorno."
            )

        print(
            f"TRADING BLOCCATO: {reason}"
        )

        return False

    # --------------------------------------------------------
    # 3 PERDITE CONSECUTIVE
    # --------------------------------------------------------

    if (
        consecutive_losses
        >= config.MAX_CONSECUTIVE_LOSSES
    ):

        reason = (
            f"{consecutive_losses} "
            "perdite consecutive"
        )

        if not already_blocked:

            state.block_trading(
                reason
            )

            send_telegram_message(
                "🛑 CRYPTO BOT BLOCCATO\n\n"
                f"{consecutive_losses} "
                "trade consecutivi in perdita.\n\n"
                "Nessun nuovo trade verrà aperto."
            )

        print(
            f"TRADING BLOCCATO: {reason}"
        )

        return False

    # --------------------------------------------------------
    # BLOCCO GIÀ PRESENTE
    # --------------------------------------------------------

    if already_blocked:

        print(
            "TRADING BLOCCATO: "
            f"{block_reason}"
        )

        return False

    print(
        "Risk control: OK"
    )

    return True
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
        "\n" + "=" * 60
    )

    print(
        f"CRYPTO BOT START - {now}"
    )

    print(
        f"MODE: {config.TRADING_MODE}"
    )

    print(
        "=" * 60
    )

    if config.TRADING_MODE not in (
        "PAPER",
        "LIVE",
    ):
        raise RuntimeError(
            "TRADING_MODE deve essere "
            "PAPER oppure LIVE"
        )

    if (
        config.TRADING_MODE == "LIVE"
        and not config.ALLOW_LIVE_TRADING
    ):
        raise RuntimeError(
            "LIVE richiesto ma "
            "ALLOW_LIVE_TRADING non è true"
        )

    kraken = KrakenClient()

    # Firestore è necessario
    # soprattutto in LIVE.
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
            f"ERRORE KRAKEN BALANCE: {e}"
        )

        return

    print(
        f"Saldo EUR Kraken: "
        f"{balance:.2f}"
    )

    if balance <= 0:
        return

    operating_capital = min(
        balance,
        config.CAPITAL_EUR
    )

    print(
        f"Capitale operativo bot: "
        f"{operating_capital:.2f} EUR"
    )

    print(
        "Rischio massimo per trade: "
        f"{operating_capital * config.RISK_PER_TRADE:.2f} EUR"
    )

    # ========================================================
    # PRIMA CONTROLLA EVENTUALE TRADE REALE
    # ========================================================

    try:

        active_trade = (
            state.get_active_trade()
        )

    except Exception as e:

        print(
            f"ERRORE FIRESTORE: {e}"
        )

        return

    if active_trade:

        if config.TRADING_MODE == "LIVE":

            monitor_active_trade(
                kraken,
                state,
                active_trade,
            )

        else:

            print(
                "Stato trade Firestore presente, "
                "ma bot in PAPER."
            )

        print(
            "\n" + "=" * 60
        )

        print(
            "CRYPTO BOT END"
        )

        print(
            "=" * 60
        )

        return

    # ========================================================
    # CONTROLLO KRAKEN
    # ========================================================

    try:

        positions = (
            kraken.get_open_positions()
        )

        orders = (
            kraken.get_open_orders()
        )

        if positions:

            print(
                "Kraken segnala una posizione "
                "non presente in Firestore."
            )

            send_telegram_message(
                "🚨 ATTENZIONE CRYPTO BOT\n\n"
                "Kraken segnala una posizione "
                "aperta non registrata "
                "in Firestore.\n"
                "Nessun nuovo trade verrà aperto."
            )

            return

        if orders:

            print(
                "Kraken segnala ordini aperti."
            )

            return

    except Exception as e:

        print(
            f"ERRORE CONTROLLO KRAKEN: {e}"
        )

        return

    # ========================================================
    # AI GUARD
    # ========================================================

    try:

        guard = AnthropicGuard()

    except Exception as e:

        print(
            f"ERRORE AI: {e}"
        )

        return

    # ========================================================
    # ANALISI BTC / ETH
    # ========================================================

    for symbol, pair_info in (
        config.PAIRS.items()
    ):

        pair = pair_info[
            "pair"
        ]

        allocation_pct = pair_info[
            "allocation_pct"
        ]

        min_notional = pair_info[
            "min_notional_eur"
        ]

        print(
            "\n" + "-" * 60
        )

        print(
            f"ANALISI {symbol}"
        )

        print(
            "-" * 60
        )

        target_notional = (
            operating_capital
            * allocation_pct
        )

        print(
            f"Allocazione: "
            f"{allocation_pct * 100:.1f}%"
        )

        print(
            f"Controvalore previsto: "
            f"{target_notional:.2f} EUR"
        )

        try:

            h4 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES[
                    "TREND"
                ],
            )

            h1 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES[
                    "CONFIRMATION"
                ],
            )

            m15 = kraken.get_ohlc(
                pair,
                config.TIMEFRAMES[
                    "ENTRY"
                ],
            )

        except Exception as e:

            print(
                f"Errore dati {symbol}: {e}"
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

        try:

            analysis = analyze_market(
                h4,
                h1,
                m15,
                symbol,
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

        if analysis.get(
            "action"
        ) not in (
            "BUY",
            "SELL",
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

        sizing = calculate_position_size(
            capital=operating_capital,
            allocation_pct=
            allocation_pct,
            entry=entry,
            stop_loss=stop_loss,
            min_notional=min_notional,
        )

        if not sizing[
            "allowed"
        ]:

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
            "actual_risk"
        ]

        # ====================================================
        # AI
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

        try:

            ai_result = (
                guard.evaluate_market_risk(
                    asset=symbol,
                    side=side,
                    current_price=entry,
                    technical_data=
                    technical_data,
                )
            )

        except Exception as e:

            print(
                f"AI Guard error: {e}"
            )

            continue

        print(
            f"AI decision: "
            f"{ai_result['decision']}"
        )

        if (
            ai_result[
                "decision"
            ]
            != "GO"
        ):

            print(
                "Trade bloccato da AI."
            )

            continue

        # ====================================================
        # PAPER
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
                "Nessun ordine inviato."
            )

            continue

        # ====================================================
        # LIVE
        # ====================================================

        if symbol == "BTC":
            leverage = (
                config.LEVERAGE_BTC
            )
        else:
            leverage = (
                config.LEVERAGE_ETH
            )

        # Identificativo candela M15
        try:

            signal_candle = (
                m15.iloc[-1][
                    "time"
                ].isoformat()
            )

        except Exception:

            signal_candle = None

        # Prima salviamo intenzione
        # su Firestore.
        state.create_trade(
            symbol=symbol,
            pair=pair,
            side=side,
            requested_entry_price=
            entry,
            requested_volume=
            quantity,
            stop_loss=stop_loss,
            take_profit=
            take_profit,
            leverage=leverage,
            signal_candle=
            signal_candle,
        )

        try:

            entry_result = (
                kraken.create_market_order(
                    pair=pair,
                    side=side,
                    volume=quantity,
                    leverage=leverage,
                    validate=False,
                )
            )

            entry_txid = extract_txid(
                entry_result
            )

            if not entry_txid:

                raise RuntimeError(
                    "TXID Entry "
                    "non restituito da Kraken"
                )

            state.set_entry_order(
                entry_txid
            )

            print(
                "ENTRY INVIATA: "
                f"{entry_txid}"
            )

        except Exception as e:

            print(
                f"ENTRY FALLITA: {e}"
            )

            state.clear_trade()

            continue

        # Market order normalmente
        # viene eseguito rapidamente.
        # Aspettiamo brevemente.
        for _ in range(10):

            time.sleep(1)

            try:

                order = (
                    kraken.get_order_info(
                        entry_txid
                    )
                )

            except Exception:
                continue

            if order_is_filled(
                order
            ):

                fill_price = (
                    get_fill_price(
                        order,
                        entry,
                    )
                )

                filled_volume = (
                    get_filled_volume(
                        order,
                        quantity,
                    )
                )

                state.mark_entry_filled(
                    fill_price=
                    fill_price,
                    filled_volume=
                    filled_volume,
                )

                break

        # Il prossimo ciclo oppure
        # questo stesso codice di monitoraggio
        # costruirà le protezioni.
        trade = (
            state.get_active_trade()
        )

        if trade:

            monitor_active_trade(
                kraken,
                state,
                trade,
            )

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


if __name__ == "__main__":
    run()
