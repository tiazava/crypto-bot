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
# TELEGRAM SICURO
# Un errore Telegram NON deve interrompere la gestione trade.
# ============================================================

def safe_telegram(message):

    try:
        send_telegram_message(
            message
        )

    except Exception as e:

        print(
            f"ERRORE TELEGRAM: {e}"
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
            "reason": "Stop Loss non valido",
        }

    target_notional = (
        capital
        * allocation_pct
    )

    if (
        target_notional
        < min_notional
    ):

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
        target_notional
        / entry
    )

    actual_risk = (
        quantity
        * stop_distance
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

def extract_txid(
    result
):

    if not result:
        return None

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

def order_is_filled(
    order
):

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

        vol_exec = 0.0

    return (
        status == "closed"
        and
        vol_exec > 0
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


def get_order_fee(
    order
):

    try:

        return float(
            order.get(
                "fee",
                0
            )
        )

    except Exception:

        return 0.0


def get_order_close_time(
    order
):

    try:

        return float(
            order.get(
                "closetm",
                0
            )
        )

    except Exception:

        return 0.0


# ============================================================
# IDENTIFICATIVO CANDELA M15
# ============================================================

def get_candle_id(
    df
):

    if (
        df is None
        or df.empty
    ):

        return None

    try:

        value = (
            df.iloc[-1]["time"]
        )

        if hasattr(
            value,
            "isoformat"
        ):

            return (
                value.isoformat()
            )

        return str(
            value
        )

    except Exception:

        try:

            return str(
                df.index[-1]
            )

        except Exception:

            return None


# ============================================================
# PNL LORDO
# ============================================================

def calculate_pnl(
    side,
    entry,
    exit_price,
    volume,
):

    if (
        side.upper()
        == "BUY"
    ):

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
# PNL NETTO COMMISSIONI
# ============================================================

def calculate_net_pnl(
    side,
    entry,
    exit_price,
    volume,
    entry_fee=0.0,
    exit_fee=0.0,
):

    gross_pnl = (
        calculate_pnl(
            side=
                side,

            entry=
                entry,

            exit_price=
                exit_price,

            volume=
                volume,
        )
    )

    total_fees = (
        float(entry_fee)
        +
        float(exit_fee)
    )

    net_pnl = (
        gross_pnl
        -
        total_fees
    )

    return {
        "gross_pnl":
            float(
                gross_pnl
            ),

        "fees":
            float(
                total_fees
            ),

        "net_pnl":
            float(
                net_pnl
            ),
    }


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

        print(
            "Impossibile cancellare "
            f"{txid}: {e}"
        )


# ============================================================
# RICONCILIA ORDINE CON CLIENT ORDER ID
# ============================================================

def recover_order_by_client_id(
    kraken,
    client_order_id
):

    if not client_order_id:
        return None

    try:

        recovered = (
            kraken
            .find_order_by_client_order_id(
                client_order_id
            )
        )

    except Exception as e:

        print(
            "Errore ricerca cl_ord_id "
            f"{client_order_id}: {e}"
        )

        return None

    if not recovered:

        return None

    print(
        "ORDINE RECUPERATO DA KRAKEN "
        f"cl_ord_id={client_order_id} "
        f"txid={recovered.get('txid')} "
        f"source={recovered.get('source')}"
    )

    return recovered


# ============================================================
# CONTROLLO LIMITI RISCHIO
# ============================================================

def check_risk_limits(
    state,
    operating_capital,
):

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

    already_blocked = bool(
        risk.get(
            "trading_blocked",
            False
        )
    )

    block_reason = (
        risk.get(
            "block_reason"
        )
    )

    max_daily_loss_eur = (
        operating_capital
        * config.MAX_DAILY_LOSS
    )

    print(
        "\nRISK CONTROL"
    )

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

    # ========================================================
    # MAX DAILY LOSS
    # ========================================================

    if (
        daily_pnl
        <= -max_daily_loss_eur
    ):

        reason = (
            "Limite perdita giornaliera "
            f"raggiunto: "
            f"{daily_pnl:.2f} EUR"
        )

        if not already_blocked:

            state.block_trading(
                reason
            )

            safe_telegram(
                "🛑 CRYPTO BOT BLOCCATO\n\n"
                "Limite perdita giornaliera "
                "raggiunto.\n"
                f"P&L oggi: "
                f"{daily_pnl:.2f} EUR\n"
                f"Limite: "
                f"-{max_daily_loss_eur:.2f} EUR\n\n"
                "Nessun nuovo trade "
                "fino al prossimo giorno."
            )

        print(
            f"TRADING BLOCCATO: "
            f"{reason}"
        )

        return False

    # ========================================================
    # MAX PERDITE CONSECUTIVE
    # ========================================================

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

            safe_telegram(
                "🛑 CRYPTO BOT BLOCCATO\n\n"
                f"{consecutive_losses} "
                "trade consecutivi "
                "in perdita.\n\n"
                "Nessun nuovo trade "
                "verrà aperto."
            )

        print(
            f"TRADING BLOCCATO: "
            f"{reason}"
        )

        return False

    # ========================================================
    # BLOCCO GIÀ PRESENTE
    # ========================================================

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
# RECUPERO ENTRY DOPO CRASH
# ============================================================

def recover_pending_entry(
    kraken,
    state,
    trade
):

    entry_txid = (
        trade.get(
            "entry_txid"
        )
    )

    if entry_txid:

        return {
            "txid":
                entry_txid,

            "order":
                None,
        }

    client_order_id = (
        trade.get(
            "entry_client_order_id"
        )
    )

    if not client_order_id:

        print(
            "ERRORE CRITICO: "
            "ENTRY_PENDING senza TXID "
            "e senza client_order_id."
        )

        safe_telegram(
            "🚨 ATTENZIONE CRYPTO BOT\n\n"
            "Trade ENTRY_PENDING senza "
            "TXID e senza client order ID.\n"
            "Nessun nuovo ordine verrà aperto."
        )

        return None

    recovered = (
        recover_order_by_client_id(
            kraken,
            client_order_id
        )
    )

    if not recovered:

        print(
            "Entry non ancora trovata "
            "su Kraken tramite cl_ord_id. "
            "Nessun nuovo ordine verrà inviato."
        )

        return None

    entry_txid = (
        recovered[
            "txid"
        ]
    )

    state.set_entry_order(
        txid=
            entry_txid,

        client_order_id=
            client_order_id,
    )

    return {
        "txid":
            entry_txid,

        "order":
            recovered.get(
                "order"
            ),
    }


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

    status = (
        trade.get(
            "status"
        )
    )

    # ========================================================
    # ENTRY PENDING
    # ========================================================

    if status == "ENTRY_PENDING":

        recovery = (
            recover_pending_entry(
                kraken,
                state,
                trade,
            )
        )

        if not recovery:

            return True

        entry_txid = (
            recovery[
                "txid"
            ]
        )

        order = (
            recovery.get(
                "order"
            )
        )

        if not order:

            try:

                order = (
                    kraken.get_order_info(
                        entry_txid
                    )
                )

            except Exception as e:

                print(
                    "Errore verifica entry: "
                    f"{e}"
                )

                return True

        if not order_is_filled(
            order
        ):

            print(
                "Entry presente su Kraken "
                "ma non ancora eseguita."
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
            fill_price=
                fill_price,

            filled_volume=
                filled_volume,
        )

        trade = (
            state.get_active_trade()
        )

        status = (
            "ENTRY_FILLED"
        )

        print(
            "Entry eseguita e "
            "registrata in Firestore."
        )

    # ========================================================
    # ENTRY FILLED / PROTECTION PENDING
    # ========================================================

    if status in {
        "ENTRY_FILLED",
        "PROTECTION_PENDING",
    }:

        pair = (
            trade[
                "pair"
            ]
        )

        side = (
            trade[
                "side"
            ]
        )

        volume = (
            trade.get(
                "entry_filled_volume"
            )
            or
            trade[
                "requested_volume"
            ]
        )

        leverage = (
            trade[
                "leverage"
            ]
        )

        stop_loss = (
            trade[
                "stop_loss"
            ]
        )

        take_profit = (
            trade[
                "take_profit"
            ]
        )

        state.mark_protection_pending()

        trade = (
            state.get_active_trade()
        )

        # ====================================================
        # STOP LOSS
        # ====================================================

        stop_txid = (
            trade.get(
                "stop_txid"
            )
        )

        stop_client_id = (
            trade.get(
                "stop_client_order_id"
            )
        )

        if (
            not stop_txid
            and stop_client_id
        ):

            recovered_stop = (
                recover_order_by_client_id(
                    kraken,
                    stop_client_id
                )
            )

            if recovered_stop:

                stop_txid = (
                    recovered_stop[
                        "txid"
                    ]
                )

                state.set_stop_order(
                    txid=
                        stop_txid,

                    client_order_id=
                        stop_client_id,
                )

        if not stop_txid:

            if not stop_client_id:

                stop_client_id = (
                    kraken.generate_client_order_id(
                        "stop"
                    )
                )

                # Salviamo PRIMA dell'AddOrder.
                state.set_stop_order(
                    txid=None,
                    client_order_id=
                        stop_client_id,
                )

            try:

                stop_result = (
                    kraken.create_stop_loss_order(
                        pair=
                            pair,

                        entry_side=
                            side,

                        volume=
                            volume,

                        stop_price=
                            stop_loss,

                        leverage=
                            leverage,

                        validate=
                            False,

                        reduce_only=
                            True,

                        client_order_id=
                            stop_client_id,
                    )
                )

                stop_txid = (
                    extract_txid(
                        stop_result
                    )
                )

                if not stop_txid:

                    raise RuntimeError(
                        "Kraken non ha restituito "
                        "TXID Stop Loss"
                    )

                state.set_stop_order(
                    txid=
                        stop_txid,

                    client_order_id=
                        stop_client_id,
                )

            except Exception as e:

                print(
                    "Errore invio Stop Loss: "
                    f"{e}"
                )

                # Potrebbe essere stato accettato
                # nonostante un errore di rete.
                recovered_stop = (
                    recover_order_by_client_id(
                        kraken,
                        stop_client_id
                    )
                )

                if recovered_stop:

                    stop_txid = (
                        recovered_stop[
                            "txid"
                        ]
                    )

                    state.set_stop_order(
                        txid=
                            stop_txid,

                        client_order_id=
                            stop_client_id,
                    )

                else:

                    safe_telegram(
                        "🚨 ERRORE STOP LOSS\n\n"
                        f"{trade['symbol']} "
                        f"{side}\n"
                        "Stop Loss non confermato "
                        "su Kraken.\n"
                        "Avvio chiusura "
                        "di emergenza."
                    )

                    return (
                        emergency_close_trade(
                            kraken,
                            state,
                            trade,
                        )
                    )

        # ====================================================
        # TAKE PROFIT
        # ====================================================

        trade = (
            state.get_active_trade()
        )

        tp_txid = (
            trade.get(
                "take_profit_txid"
            )
        )

        tp_client_id = (
            trade.get(
                "take_profit_client_order_id"
            )
        )

        if (
            not tp_txid
            and tp_client_id
        ):

            recovered_tp = (
                recover_order_by_client_id(
                    kraken,
                    tp_client_id
                )
            )

            if recovered_tp:

                tp_txid = (
                    recovered_tp[
                        "txid"
                    ]
                )

                state.set_take_profit_order(
                    txid=
                        tp_txid,

                    client_order_id=
                        tp_client_id,
                )

        if not tp_txid:

            if not tp_client_id:

                tp_client_id = (
                    kraken.generate_client_order_id(
                        "take_profit"
                    )
                )

                # Anche TP viene salvato
                # PRIMA di Kraken.
                state.set_take_profit_order(
                    txid=None,
                    client_order_id=
                        tp_client_id,
                )

            try:

                tp_result = (
                    kraken.create_take_profit_order(
                        pair=
                            pair,

                        entry_side=
                            side,

                        volume=
                            volume,

                        take_profit_price=
                            take_profit,

                        leverage=
                            leverage,

                        validate=
                            False,

                        reduce_only=
                            True,

                        client_order_id=
                            tp_client_id,
                    )
                )

                tp_txid = (
                    extract_txid(
                        tp_result
                    )
                )

                if not tp_txid:

                    raise RuntimeError(
                        "Kraken non ha restituito "
                        "TXID Take Profit"
                    )

                state.set_take_profit_order(
                    txid=
                        tp_txid,

                    client_order_id=
                        tp_client_id,
                )

            except Exception as e:

                print(
                    "Errore invio Take Profit: "
                    f"{e}"
                )

                recovered_tp = (
                    recover_order_by_client_id(
                        kraken,
                        tp_client_id
                    )
                )

                if recovered_tp:

                    tp_txid = (
                        recovered_tp[
                            "txid"
                        ]
                    )

                    state.set_take_profit_order(
                        txid=
                            tp_txid,

                        client_order_id=
                            tp_client_id,
                    )

                else:

                    safe_telegram(
                        "🚨 ERRORE TAKE PROFIT\n\n"
                        f"{trade['symbol']} "
                        f"{side}\n"
                        "Take Profit non confermato "
                        "su Kraken.\n"
                        "Avvio chiusura "
                        "di emergenza."
                    )

                    return (
                        emergency_close_trade(
                            kraken,
                            state,
                            trade,
                        )
                    )

        # ====================================================
        # ENTRAMBE LE PROTEZIONI PRESENTI
        # ====================================================

        state.mark_protected()

        trade = (
            state.get_active_trade()
        )

        print(
            "Posizione protetta "
            "con SL + TP."
        )

        if not trade.get(
            "telegram_open_sent"
        ):

            entry_price = float(
                trade.get(
                    "entry_fill_price"
                )
                or
                trade[
                    "requested_entry_price"
                ]
            )

            notional = (
                float(volume)
                * entry_price
            )

            risk = (
                abs(
                    entry_price
                    -
                    float(
                        stop_loss
                    )
                )
                *
                float(volume)
            )

            try:

                notify_trade_open(
                    symbol=
                        trade[
                            "symbol"
                        ],

                    side=
                        side,

                    entry=
                        entry_price,

                    stop_loss=
                        float(
                            stop_loss
                        ),

                    take_profit=
                        float(
                            take_profit
                        ),

                    notional=
                        float(
                            notional
                        ),

                    risk=
                        float(
                            risk
                        ),
                )

                state.mark_telegram_open_sent()

            except Exception as e:

                print(
                    "Errore Telegram apertura: "
                    f"{e}"
                )

        return True

    # ========================================================
    # PROTECTED
    # ========================================================

    if status == "PROTECTED":

        stop_txid = (
            trade.get(
                "stop_txid"
            )
        )

        tp_txid = (
            trade.get(
                "take_profit_txid"
            )
        )

        try:

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

        except Exception as e:

            print(
                "Errore lettura SL/TP: "
                f"{e}"
            )

            return True

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

        # ====================================================
        # EVENTUALITÀ ANOMALA: ENTRAMBI CLOSED
        # ====================================================

        if (
            stop_filled
            and tp_filled
        ):

            print(
                "ATTENZIONE: Kraken riporta "
                "SL e TP entrambi closed."
            )

            safe_telegram(
                "🚨 ANOMALIA KRAKEN\n\n"
                f"{trade['symbol']}: "
                "SL e TP risultano entrambi "
                "closed. Il bot userà "
                "l'ordine chiuso per primo."
            )

            stop_time = (
                get_order_close_time(
                    stop_order
                )
            )

            tp_time = (
                get_order_close_time(
                    tp_order
                )
            )

            if (
                stop_time > 0
                and tp_time > 0
            ):

                if stop_time <= tp_time:

                    tp_filled = False

                else:

                    stop_filled = False

        # ====================================================
        # TAKE PROFIT
        # ====================================================

        if tp_filled:

            return (
                finalize_trade_exit(
                    kraken=
                        kraken,

                    state=
                        state,

                    trade=
                        trade,

                    exit_order=
                        tp_order,

                    exit_reason=
                        "TAKE_PROFIT",

                    opposite_txid=
                        stop_txid,
                )
            )

        # ====================================================
        # STOP LOSS
        # ====================================================

        if stop_filled:

            return (
                finalize_trade_exit(
                    kraken=
                        kraken,

                    state=
                        state,

                    trade=
                        trade,

                    exit_order=
                        stop_order,

                    exit_reason=
                        "STOP_LOSS",

                    opposite_txid=
                        tp_txid,
                )
            )

        print(
            "Trade ancora aperto "
            "e protetto."
        )

        return True

    # ========================================================
    # EXIT PENDING
    # ========================================================

    if status == "EXIT_PENDING":

        print(
            "Uscita già richiesta. "
            "Verifica posizione Kraken."
        )

        try:

            positions = (
                kraken.get_open_positions()
            )

        except Exception as e:

            print(
                "Impossibile verificare "
                f"le posizioni: {e}"
            )

            return True

        if positions:

            print(
                "Kraken segnala ancora "
                "almeno una posizione aperta."
            )

            return True

        # Non registriamo un P&L inventato
        # per una chiusura di emergenza.
        state.close_trade(
            close_reason=
                trade.get(
                    "close_reason",
                    "EXIT_CONFIRMED"
                )
        )

        print(
            "Kraken non segnala più "
            "posizioni aperte. "
            "Trade marcato CLOSED."
        )

        return True

    return True


# ============================================================
# CHIUSURA EMERGENZA
# ============================================================

def emergency_close_trade(
    kraken,
    state,
    trade,
):

    pair = (
        trade[
            "pair"
        ]
    )

    side = (
        trade[
            "side"
        ]
    )

    volume = (
        trade.get(
            "entry_filled_volume"
        )
        or
        trade[
            "requested_volume"
        ]
    )

    leverage = (
        trade[
            "leverage"
        ]
    )

    # Cancella solo le protezioni
    # di cui conosciamo il TXID.
    safe_cancel(
        kraken,
        trade.get(
            "stop_txid"
        )
    )

    safe_cancel(
        kraken,
        trade.get(
            "take_profit_txid"
        )
    )

    emergency_client_id = (
        kraken.generate_client_order_id(
            "emergency"
        )
    )

    try:

        result = (
            kraken.close_position_market(
                pair=
                    pair,

                entry_side=
                    side,

                volume=
                    volume,

                leverage=
                    leverage,

                validate=
                    False,

                client_order_id=
                    emergency_client_id,
            )
        )

        emergency_txid = (
            extract_txid(
                result
            )
        )

        if not emergency_txid:

            raise RuntimeError(
                "TXID chiusura emergenza "
                "non restituito"
            )

        state.mark_exit_pending(
            "EMERGENCY_PROTECTION_FAILURE"
        )

        print(
            "Chiusura emergenza inviata: "
            f"{emergency_txid}"
        )

        safe_telegram(
            "🚨 CHIUSURA EMERGENZA INVIATA\n\n"
            f"Asset: "
            f"{trade['symbol']}\n"
            "Motivo: protezioni SL/TP "
            "non confermate.\n"
            "Il bot controllerà Kraken "
            "nelle prossime esecuzioni."
        )

        return True

    except Exception as e:

        print(
            "ERRORE CRITICO "
            "CHIUSURA EMERGENZA: "
            f"{e}"
        )

        safe_telegram(
            "🚨🚨 ATTENZIONE CRITICA\n\n"
            f"{trade['symbol']} potrebbe "
            "avere una posizione "
            "non correttamente protetta.\n"
            "Chiusura automatica "
            "di emergenza fallita.\n\n"
            "Controllare Kraken."
        )

        # Lasciamo il trade attivo.
        # Il bot NON aprirà altro.
        return True


# ============================================================
# FINALIZZA TAKE PROFIT / STOP LOSS
# ============================================================

def finalize_trade_exit(
    kraken,
    state,
    trade,
    exit_order,
    exit_reason,
    opposite_txid,
):

    print(
        f"{exit_reason} ESEGUITO"
    )

    state.mark_exit_pending(
        exit_reason
    )

    safe_cancel(
        kraken,
        opposite_txid
    )

    entry_price = float(
        trade.get(
            "entry_fill_price"
        )
        or
        trade[
            "requested_entry_price"
        ]
    )

    volume = float(
        trade.get(
            "entry_filled_volume"
        )
        or
        trade[
            "requested_volume"
        ]
    )

    if (
        exit_reason
        == "TAKE_PROFIT"
    ):

        fallback_exit = (
            trade[
                "take_profit"
            ]
        )

    else:

        fallback_exit = (
            trade[
                "stop_loss"
            ]
        )

    exit_price = (
        get_fill_price(
            exit_order,
            fallback_exit
        )
    )

    # ========================================================
    # COMMISSIONE ENTRY
    # ========================================================

    entry_fee = 0.0

    entry_txid = (
        trade.get(
            "entry_txid"
        )
    )

    if entry_txid:

        try:

            entry_order = (
                kraken.get_order_info(
                    entry_txid
                )
            )

            entry_fee = (
                get_order_fee(
                    entry_order
                )
            )

        except Exception as e:

            print(
                "Impossibile recuperare "
                f"fee entry: {e}"
            )

    # ========================================================
    # COMMISSIONE EXIT
    # ========================================================

    exit_fee = (
        get_order_fee(
            exit_order
        )
    )

    pnl_data = (
        calculate_net_pnl(
            side=
                trade[
                    "side"
                ],

            entry=
                entry_price,

            exit_price=
                exit_price,

            volume=
                volume,

            entry_fee=
                entry_fee,

            exit_fee=
                exit_fee,
        )
    )

    pnl = (
        pnl_data[
            "net_pnl"
        ]
    )

    print(
        f"P&L lordo: "
        f"{pnl_data['gross_pnl']:.4f} EUR"
    )

    print(
        f"Commissioni rilevate: "
        f"{pnl_data['fees']:.4f} EUR"
    )

    print(
        f"P&L netto: "
        f"{pnl:.4f} EUR"
    )

    # ========================================================
    # PRIMA CHIUDIAMO LO STATO
    # Poi Telegram.
    # ========================================================

    state.close_trade(
        close_reason=
            exit_reason,

        exit_price=
            exit_price,

        pnl_eur=
            pnl,
    )

    try:

        if (
            not trade.get(
                "telegram_close_sent"
            )
        ):

            if (
                exit_reason
                == "TAKE_PROFIT"
            ):

                notify_take_profit(
                    symbol=
                        trade[
                            "symbol"
                        ],

                    side=
                        trade[
                            "side"
                        ],

                    entry=
                        entry_price,

                    exit_price=
                        exit_price,

                    profit=
                        pnl,
                )

            else:

                notify_stop_loss(
                    symbol=
                        trade[
                            "symbol"
                        ],

                    side=
                        trade[
                            "side"
                        ],

                    entry=
                        entry_price,

                    exit_price=
                        exit_price,

                    loss=
                        pnl,
                )

            state.mark_telegram_close_sent()

    except Exception as e:

        print(
            "Errore Telegram chiusura: "
            f"{e}"
        )

    return True


# ============================================================
# MAIN
# ============================================================

def run():

    now = (
        datetime.now(
            timezone.utc
        )
        .strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )

    print(
        "\n" + "=" * 60
    )

    print(
        f"CRYPTO BOT START - {now}"
    )

    print(
        f"MODE: "
        f"{config.TRADING_MODE}"
    )

    print(
        "=" * 60
    )

    # ========================================================
    # MODALITÀ
    # ========================================================

    if (
        config.TRADING_MODE
        not in (
            "PAPER",
            "LIVE",
        )
    ):

        raise RuntimeError(
            "TRADING_MODE deve essere "
            "PAPER oppure LIVE"
        )

    if (
        config.TRADING_MODE
        == "LIVE"
        and
        not config.ALLOW_LIVE_TRADING
    ):

        raise RuntimeError(
            "LIVE richiesto ma "
            "ALLOW_LIVE_TRADING "
            "non è true"
        )

    kraken = (
        KrakenClient()
    )

    state = (
        TradeState()
    )

    # ========================================================
    # SALDO
    # ========================================================

    try:

        balance = (
            kraken.get_account_balance()
        )

    except Exception as e:

        print(
            "ERRORE KRAKEN BALANCE: "
            f"{e}"
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
        "Capitale operativo bot: "
        f"{operating_capital:.2f} EUR"
    )

    print(
        "Rischio massimo per trade: "
        f"{operating_capital * config.RISK_PER_TRADE:.2f} EUR"
    )

    # ========================================================
    # TRADE ATTIVO
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

        if (
            config.TRADING_MODE
            == "LIVE"
        ):

            monitor_active_trade(
                kraken,
                state,
                active_trade,
            )

        else:

            print(
                "Trade Firestore presente "
                "ma bot in PAPER."
            )

        return

    # ========================================================
    # RISK CONTROL
    # ========================================================

    try:

        risk_allowed = (
            check_risk_limits(
                state=
                    state,

                operating_capital=
                    operating_capital,
            )
        )

    except Exception as e:

        print(
            "ERRORE RISK CONTROL: "
            f"{e}"
        )

        return

    if not risk_allowed:

        print(
            "Nuovi ingressi disabilitati."
        )

        return

    # ========================================================
    # KRAKEN DEVE ESSERE PULITO
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

            safe_telegram(
                "🚨 ATTENZIONE CRYPTO BOT\n\n"
                "Kraken segnala una posizione "
                "aperta non registrata "
                "in Firestore.\n"
                "Nessun nuovo trade verrà aperto."
            )

            return

        if orders:

            print(
                "Kraken segnala ordini aperti "
                "non associati al trade Firestore."
            )

            return

    except Exception as e:

        print(
            "ERRORE CONTROLLO KRAKEN: "
            f"{e}"
        )

        return

    # ========================================================
    # AI GUARD
    # ========================================================

    try:

        guard = (
            AnthropicGuard()
        )

    except Exception as e:

        print(
            f"ERRORE AI: {e}"
        )

        return

    # ========================================================
    # BTC / ETH
    # ========================================================

    for (
        symbol,
        pair_info
    ) in config.PAIRS.items():

        pair = (
            pair_info[
                "pair"
            ]
        )

        allocation_pct = (
            pair_info[
                "allocation_pct"
            ]
        )

        min_notional = (
            pair_info[
                "min_notional_eur"
            ]
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

        target_notional = (
            operating_capital
            * allocation_pct
        )

        print(
            f"Allocazione: "
            f"{allocation_pct * 100:.1f}%"
        )

        print(
            "Controvalore previsto: "
            f"{target_notional:.2f} EUR"
        )

        # ====================================================
        # DATI
        # ====================================================

        try:

            h4 = (
                kraken.get_ohlc(
                    pair,
                    config.TIMEFRAMES[
                        "TREND"
                    ],
                )
            )

            h1 = (
                kraken.get_ohlc(
                    pair,
                    config.TIMEFRAMES[
                        "CONFIRMATION"
                    ],
                )
            )

            m15 = (
                kraken.get_ohlc(
                    pair,
                    config.TIMEFRAMES[
                        "ENTRY"
                    ],
                )
            )

        except Exception as e:

            print(
                f"Errore dati "
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

        # ====================================================
        # CANDELA
        # ====================================================

        signal_candle = (
            get_candle_id(
                m15
            )
        )

        if signal_candle is None:

            print(
                "Impossibile identificare "
                "candela M15."
            )

            continue

        print(
            f"Candela M15: "
            f"{signal_candle}"
        )

        # ====================================================
        # STRATEGIA
        # ====================================================

        try:

            analysis = (
                analyze_market(
                    h4,
                    h1,
                    m15,
                    symbol,
                )
            )

        except Exception as e:

            print(
                f"Errore strategia "
                f"{symbol}: {e}"
            )

            continue

        action = (
            analysis.get(
                "action",
                "HOLD"
            )
        )

        reason = (
            analysis.get(
                "reason",
                "Nessun motivo disponibile"
            )
        )

        # ====================================================
        # IDEMPOTENZA M15
        # ====================================================

        try:

            claimed = (
                state.claim_signal_candle(
                    symbol=
                        symbol,

                    candle_id=
                        signal_candle,

                    action=
                        action,
                )
            )

        except Exception as e:

            print(
                "ERRORE IDEMPOTENZA "
                f"{symbol}: {e}"
            )

            continue

        if not claimed:

            print(
                f"SKIP {symbol}: "
                "candela M15 già processata."
            )

            continue

        try:

            state.update_signal_result(
                symbol=
                    symbol,

                candle_id=
                    signal_candle,

                action=
                    action,

                reason=
                    reason,
            )

        except Exception as e:

            print(
                "Avviso signal state: "
                f"{e}"
            )

        print(
            f"Prezzo: "
            f"{analysis.get('price')}"
        )

        print(
            f"Segnale: {action}"
        )

        print(
            f"Motivo: {reason}"
        )

        if (
            action
            not in (
                "BUY",
                "SELL",
            )
        ):

            print(
                "Nessun trade."
            )

            continue

        # ====================================================
        # SEGNALE
        # ====================================================

        side = action

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

        sizing = (
            calculate_position_size(
                capital=
                    operating_capital,

                allocation_pct=
                    allocation_pct,

                entry=
                    entry,

                stop_loss=
                    stop_loss,

                min_notional=
                    min_notional,
            )
        )

        if not sizing[
            "allowed"
        ]:

            print(
                "TRADE BLOCCATO: "
                f"{sizing['reason']}"
            )

            continue

        quantity = (
            sizing[
                "quantity"
            ]
        )

        notional = (
            sizing[
                "notional"
            ]
        )

        actual_risk = (
            sizing[
                "actual_risk"
            ]
        )

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

            "signal_candle":
                signal_candle,
        }

        try:

            ai_result = (
                guard.evaluate_market_risk(
                    asset=
                        symbol,

                    side=
                        side,

                    current_price=
                        entry,

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
            "AI decision: "
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
                "Controvalore: "
                f"{notional:.2f} EUR"
            )

            print(
                "Rischio teorico: "
                f"{actual_risk:.2f} EUR"
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

        # ====================================================
        # GENERA CLIENT ORDER ID PRIMA DI KRAKEN
        # ====================================================

        entry_client_order_id = (
            kraken.generate_client_order_id(
                "entry"
            )
        )

        print(
            "Entry client order ID: "
            f"{entry_client_order_id}"
        )

        # ====================================================
        # FIRESTORE PRIMA DELL'ORDINE
        # ====================================================

        try:

            state.create_trade(
                symbol=
                    symbol,

                pair=
                    pair,

                side=
                    side,

                requested_entry_price=
                    entry,

                requested_volume=
                    quantity,

                stop_loss=
                    stop_loss,

                take_profit=
                    take_profit,

                leverage=
                    leverage,

                signal_candle=
                    signal_candle,

                entry_client_order_id=
                    entry_client_order_id,
            )

        except Exception as e:

            print(
                "ERRORE CREAZIONE STATO "
                f"TRADE: {e}"
            )

            continue

        # ====================================================
        # ORDINE KRAKEN CON LO STESSO cl_ord_id
        # ====================================================

        try:

            entry_result = (
                kraken.create_market_order(
                    pair=
                        pair,

                    side=
                        side,

                    volume=
                        quantity,

                    leverage=
                        leverage,

                    validate=
                        False,

                    client_order_id=
                        entry_client_order_id,
                )
            )

            entry_txid = (
                extract_txid(
                    entry_result
                )
            )

            if not entry_txid:

                raise RuntimeError(
                    "TXID Entry "
                    "non restituito da Kraken"
                )

            state.set_entry_order(
                txid=
                    entry_txid,

                client_order_id=
                    entry_client_order_id,
            )

            print(
                "ENTRY INVIATA: "
                f"{entry_txid}"
            )

        except Exception as e:

            print(
                "ENTRY RISPOSTA INCERTA: "
                f"{e}"
            )

            # IMPORTANTISSIMO:
            # NON cancelliamo Firestore.
            #
            # Kraken potrebbe aver ricevuto
            # l'ordine anche se la risposta
            # non è arrivata al bot.
            #
            # La prossima esecuzione userà
            # entry_client_order_id per
            # riconciliare l'ordine.

            safe_telegram(
                "⚠️ ENTRY KRAKEN DA VERIFICARE\n\n"
                f"Asset: {symbol}\n"
                f"Side: {side}\n"
                "La risposta dell'ordine "
                "non è stata confermata.\n"
                "Il bot NON invierà "
                "un secondo ordine e proverà "
                "a recuperarlo tramite "
                "client order ID."
            )

            return

        # ====================================================
        # ATTESA BREVE FILL
        # ====================================================

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

        # ====================================================
        # MONITOR / PROTEZIONE
        # ====================================================

        trade = (
            state.get_active_trade()
        )

        if trade:

            monitor_active_trade(
                kraken,
                state,
                trade,
            )

        # MAX 1 POSIZIONE
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
