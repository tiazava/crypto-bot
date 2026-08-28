from datetime import datetime
from zoneinfo import ZoneInfo

from google.cloud import firestore


# ============================================================
# CONFIGURAZIONE FIRESTORE
# ============================================================

TRADE_COLLECTION_NAME = "trade_state"
ACTIVE_TRADE_DOCUMENT_ID = "active_trade"
RISK_DOCUMENT_ID = "risk_state"

SIGNAL_COLLECTION_NAME = "signal_state"

ROME_TZ = ZoneInfo("Europe/Rome")


class TradeState:

    def __init__(self):

        self.db = firestore.Client()

    # ========================================================
    # TEMPO
    # ========================================================

    def _now(self):

        return (
            datetime.now(
                ROME_TZ
            )
            .isoformat()
        )

    def _today(self):

        return (
            datetime.now(
                ROME_TZ
            )
            .date()
            .isoformat()
        )

    # ========================================================
    # DOCUMENT REFERENCES
    # ========================================================

    def _trade_ref(self):

        return (
            self.db
            .collection(
                TRADE_COLLECTION_NAME
            )
            .document(
                ACTIVE_TRADE_DOCUMENT_ID
            )
        )

    def _risk_ref(self):

        return (
            self.db
            .collection(
                TRADE_COLLECTION_NAME
            )
            .document(
                RISK_DOCUMENT_ID
            )
        )

    def _signal_ref(
        self,
        symbol,
    ):

        symbol = (
            str(symbol)
            .upper()
            .strip()
        )

        return (
            self.db
            .collection(
                SIGNAL_COLLECTION_NAME
            )
            .document(
                symbol
            )
        )

    # ========================================================
    # LETTURA TRADE
    # ========================================================

    def get_trade(self):

        snapshot = (
            self._trade_ref()
            .get()
        )

        if not snapshot.exists:
            return None

        data = (
            snapshot.to_dict()
        )

        if not data:
            return None

        return data

    def get_active_trade(self):

        trade = (
            self.get_trade()
        )

        if not trade:
            return None

        active_statuses = {
            "ENTRY_PENDING",
            "ENTRY_FILLED",
            "PROTECTION_PENDING",
            "PROTECTED",
            "EXIT_PENDING",
        }

        if (
            trade.get("status")
            not in active_statuses
        ):

            return None

        return trade

    # ========================================================
    # CREAZIONE TRADE
    # ========================================================

    def create_trade(
        self,
        symbol,
        pair,
        side,
        requested_entry_price,
        requested_volume,
        stop_loss,
        take_profit,
        leverage,
        signal_candle=None,
        entry_client_order_id=None,
    ):

        now = (
            self._now()
        )

        data = {

            "status":
                "ENTRY_PENDING",

            "symbol":
                str(
                    symbol
                ).upper(),

            "pair":
                pair,

            "side":
                str(
                    side
                ).upper(),

            "requested_entry_price":
                float(
                    requested_entry_price
                ),

            "requested_volume":
                float(
                    requested_volume
                ),

            "stop_loss":
                float(
                    stop_loss
                ),

            "take_profit":
                float(
                    take_profit
                ),

            "leverage":
                float(
                    leverage
                ),

            # ================================================
            # ENTRY
            # ================================================

            "entry_client_order_id":
                entry_client_order_id,

            "entry_txid":
                None,

            "entry_fill_price":
                None,

            "entry_filled_volume":
                None,

            # ================================================
            # STOP LOSS
            # ================================================

            "stop_client_order_id":
                None,

            "stop_txid":
                None,

            # ================================================
            # TAKE PROFIT
            # ================================================

            "take_profit_client_order_id":
                None,

            "take_profit_txid":
                None,

            # ================================================
            # EMERGENCY EXIT
            # ================================================

            "emergency_client_order_id":
                None,

            "emergency_txid":
                None,

            # ================================================
            # SIGNAL
            # ================================================

            "signal_candle":
                signal_candle,

            # ================================================
            # EXIT
            # ================================================

            "close_reason":
                None,

            "exit_price":
                None,

            "pnl_eur":
                None,

            # Protezione contro doppio conteggio P&L.
            "risk_result_recorded":
                False,

            "risk_result_recorded_at":
                None,

            # ================================================
            # TELEGRAM
            # ================================================

            "telegram_open_sent":
                False,

            "telegram_close_sent":
                False,

            # ================================================
            # TIMESTAMP
            # ================================================

            "created_at":
                now,

            "updated_at":
                now,
        }

        self._trade_ref().set(
            data
        )

        return data

    # ========================================================
    # ENTRY
    # ========================================================

    def set_entry_order(
        self,
        txid=None,
        client_order_id=None,
    ):

        update = {
            "entry_txid":
                txid,

            "updated_at":
                self._now(),
        }

        if client_order_id:

            update[
                "entry_client_order_id"
            ] = (
                str(
                    client_order_id
                )
            )

        self._trade_ref().update(
            update
        )

    def mark_entry_filled(
        self,
        fill_price,
        filled_volume,
    ):

        self._trade_ref().update(
            {
                "status":
                    "ENTRY_FILLED",

                "entry_fill_price":
                    float(
                        fill_price
                    ),

                "entry_filled_volume":
                    float(
                        filled_volume
                    ),

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # PROTEZIONI
    # ========================================================

    def mark_protection_pending(
        self,
    ):

        self._trade_ref().update(
            {
                "status":
                    "PROTECTION_PENDING",

                "updated_at":
                    self._now(),
            }
        )

    def set_stop_order(
        self,
        txid=None,
        client_order_id=None,
    ):

        update = {
            "stop_txid":
                txid,

            "updated_at":
                self._now(),
        }

        if client_order_id:

            update[
                "stop_client_order_id"
            ] = (
                str(
                    client_order_id
                )
            )

        self._trade_ref().update(
            update
        )

    def set_take_profit_order(
        self,
        txid=None,
        client_order_id=None,
    ):

        update = {
            "take_profit_txid":
                txid,

            "updated_at":
                self._now(),
        }

        if client_order_id:

            update[
                "take_profit_client_order_id"
            ] = (
                str(
                    client_order_id
                )
            )

        self._trade_ref().update(
            update
        )

    def mark_protected(
        self,
    ):

        trade = (
            self.get_trade()
        )

        if not trade:

            raise RuntimeError(
                "Nessun trade Firestore presente"
            )

        if not trade.get(
            "stop_txid"
        ):

            raise RuntimeError(
                "Stop Loss non presente"
            )

        if not trade.get(
            "take_profit_txid"
        ):

            raise RuntimeError(
                "Take Profit non presente"
            )

        now = (
            self._now()
        )

        self._trade_ref().update(
            {
                "status":
                    "PROTECTED",

                "protected_at":
                    now,

                "updated_at":
                    now,
            }
        )

    # ========================================================
    # EMERGENCY ORDER
    # ========================================================

    def set_emergency_order(
        self,
        txid=None,
        client_order_id=None,
    ):

        update = {
            "emergency_txid":
                txid,

            "updated_at":
                self._now(),
        }

        if client_order_id:

            update[
                "emergency_client_order_id"
            ] = (
                str(
                    client_order_id
                )
            )

        self._trade_ref().update(
            update
        )

    # ========================================================
    # EXIT PENDING
    # ========================================================

    def mark_exit_pending(
        self,
        close_reason,
    ):

        self._trade_ref().update(
            {
                "status":
                    "EXIT_PENDING",

                "close_reason":
                    close_reason,

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # CHIUSURA TRADE ATOMICA + IDEMPOTENTE
    # ========================================================

    def close_trade(
        self,
        close_reason,
        exit_price=None,
        pnl_eur=None,
    ):

        trade_ref = (
            self._trade_ref()
        )

        risk_ref = (
            self._risk_ref()
        )

        transaction = (
            self.db.transaction()
        )

        today = (
            self._today()
        )

        now = (
            self._now()
        )

        @firestore.transactional
        def close_transaction(
            transaction,
        ):

            trade_snapshot = (
                trade_ref.get(
                    transaction=transaction
                )
            )

            if not trade_snapshot.exists:

                raise RuntimeError(
                    "Trade Firestore non presente"
                )

            trade = (
                trade_snapshot.to_dict()
                or {}
            )

            # ================================================
            # DATI BASE CHIUSURA
            # ================================================

            trade_update = {

                "status":
                    "CLOSED",

                "close_reason":
                    close_reason,

                "closed_at":
                    trade.get(
                        "closed_at"
                    )
                    or now,

                "updated_at":
                    now,
            }

            if (
                exit_price
                is not None
            ):

                trade_update[
                    "exit_price"
                ] = (
                    float(
                        exit_price
                    )
                )

            if (
                pnl_eur
                is not None
            ):

                trade_update[
                    "pnl_eur"
                ] = (
                    float(
                        pnl_eur
                    )
                )

            # ================================================
            # SENZA PNL:
            # chiudiamo soltanto il trade.
            # ================================================

            if (
                pnl_eur
                is None
            ):

                transaction.update(
                    trade_ref,
                    trade_update,
                )

                return {
                    "closed":
                        True,

                    "risk_recorded":
                        False,

                    "already_recorded":
                        bool(
                            trade.get(
                                "risk_result_recorded",
                                False,
                            )
                        ),
                }

            # ================================================
            # IDEMPOTENZA RISULTATO
            # ================================================

            already_recorded = bool(
                trade.get(
                    "risk_result_recorded",
                    False,
                )
            )

            if already_recorded:

                # Trade può essere richiuso/retry,
                # ma il P&L NON viene sommato di nuovo.

                transaction.update(
                    trade_ref,
                    trade_update,
                )

                return {
                    "closed":
                        True,

                    "risk_recorded":
                        False,

                    "already_recorded":
                        True,
                }

            # ================================================
            # LETTURA RISK NELLA STESSA TRANSAZIONE
            # ================================================

            risk_snapshot = (
                risk_ref.get(
                    transaction=transaction
                )
            )

            if risk_snapshot.exists:

                risk = (
                    risk_snapshot.to_dict()
                    or {}
                )

            else:

                risk = {}

            # ================================================
            # RESET GIORNO
            # ================================================

            if (
                risk.get("date")
                != today
            ):

                daily_pnl = 0.0

                consecutive_losses = int(
                    risk.get(
                        "consecutive_losses",
                        0,
                    )
                )

                trading_blocked = False
                block_reason = None

            else:

                daily_pnl = float(
                    risk.get(
                        "daily_pnl_eur",
                        0.0,
                    )
                )

                consecutive_losses = int(
                    risk.get(
                        "consecutive_losses",
                        0,
                    )
                )

                trading_blocked = bool(
                    risk.get(
                        "trading_blocked",
                        False,
                    )
                )

                block_reason = (
                    risk.get(
                        "block_reason"
                    )
                )

            pnl_value = (
                float(
                    pnl_eur
                )
            )

            daily_pnl += (
                pnl_value
            )

            if pnl_value < 0:

                consecutive_losses += 1

            else:

                consecutive_losses = 0

            risk_update = {

                "date":
                    today,

                "daily_pnl_eur":
                    float(
                        daily_pnl
                    ),

                "consecutive_losses":
                    int(
                        consecutive_losses
                    ),

                "trading_blocked":
                    trading_blocked,

                "block_reason":
                    block_reason,

                "updated_at":
                    now,
            }

            # ================================================
            # MARCA RISULTATO REGISTRATO
            # NELLA STESSA TRANSAZIONE
            # ================================================

            trade_update[
                "risk_result_recorded"
            ] = True

            trade_update[
                "risk_result_recorded_at"
            ] = now

            transaction.set(
                risk_ref,
                risk_update,
                merge=True,
            )

            transaction.update(
                trade_ref,
                trade_update,
            )

            return {
                "closed":
                    True,

                "risk_recorded":
                    True,

                "already_recorded":
                    False,

                "daily_pnl_eur":
                    daily_pnl,

                "consecutive_losses":
                    consecutive_losses,
            }

        return (
            close_transaction(
                transaction
            )
        )

    # ========================================================
    # TELEGRAM
    # ========================================================

    def mark_telegram_open_sent(
        self,
    ):

        self._trade_ref().update(
            {
                "telegram_open_sent":
                    True,

                "updated_at":
                    self._now(),
            }
        )

    def mark_telegram_close_sent(
        self,
    ):

        self._trade_ref().update(
            {
                "telegram_close_sent":
                    True,

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # ERRORI
    # ========================================================

    def mark_error(
        self,
        message,
    ):

        self._trade_ref().update(
            {
                "status":
                    "ERROR",

                "error_message":
                    str(
                        message
                    ),

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # CANCELLA TRADE
    # Solo manutenzione/test.
    # ========================================================

    def clear_trade(
        self,
    ):

        self._trade_ref().delete()

    # ========================================================
    # RISK STATE DEFAULT
    # ========================================================

    def _default_risk_state(
        self,
    ):

        return {

            "date":
                self._today(),

            "daily_pnl_eur":
                0.0,

            "consecutive_losses":
                0,

            "trading_blocked":
                False,

            "block_reason":
                None,

            "updated_at":
                self._now(),
        }

    # ========================================================
    # LETTURA RISK STATE
    # ========================================================

    def get_risk_state(
        self,
    ):

        risk_ref = (
            self._risk_ref()
        )

        snapshot = (
            risk_ref.get()
        )

        if not snapshot.exists:

            data = (
                self._default_risk_state()
            )

            risk_ref.set(
                data
            )

            return data

        data = (
            snapshot.to_dict()
            or {}
        )

        if not data:

            data = (
                self._default_risk_state()
            )

            risk_ref.set(
                data
            )

            return data

        # ================================================
        # NUOVO GIORNO OPERATIVO - EUROPE/ROME
        # ================================================

        if (
            data.get("date")
            != self._today()
        ):

            consecutive_losses = int(
                data.get(
                    "consecutive_losses",
                    0,
                )
            )

            data = {

                "date":
                    self._today(),

                "daily_pnl_eur":
                    0.0,

                "consecutive_losses":
                    consecutive_losses,

                "trading_blocked":
                    False,

                "block_reason":
                    None,

                "updated_at":
                    self._now(),
            }

            risk_ref.set(
                data
            )

        return data

    # ========================================================
    # RECORD TRADE RESULT
    #
    # Manteniamo questa funzione per compatibilità,
    # ma la chiusura normale deve usare close_trade(),
    # che è atomica e idempotente.
    # ========================================================

    def record_trade_result(
        self,
        pnl_eur,
    ):

        risk_ref = (
            self._risk_ref()
        )

        transaction = (
            self.db.transaction()
        )

        today = (
            self._today()
        )

        now = (
            self._now()
        )

        pnl_value = (
            float(
                pnl_eur
            )
        )

        @firestore.transactional
        def record(
            transaction,
        ):

            snapshot = (
                risk_ref.get(
                    transaction=transaction
                )
            )

            if snapshot.exists:

                risk = (
                    snapshot.to_dict()
                    or {}
                )

            else:

                risk = {}

            if (
                risk.get("date")
                != today
            ):

                daily_pnl = 0.0

                consecutive_losses = int(
                    risk.get(
                        "consecutive_losses",
                        0,
                    )
                )

                trading_blocked = False
                block_reason = None

            else:

                daily_pnl = float(
                    risk.get(
                        "daily_pnl_eur",
                        0.0,
                    )
                )

                consecutive_losses = int(
                    risk.get(
                        "consecutive_losses",
                        0,
                    )
                )

                trading_blocked = bool(
                    risk.get(
                        "trading_blocked",
                        False,
                    )
                )

                block_reason = (
                    risk.get(
                        "block_reason"
                    )
                )

            daily_pnl += (
                pnl_value
            )

            if pnl_value < 0:

                consecutive_losses += 1

            else:

                consecutive_losses = 0

            update = {

                "date":
                    today,

                "daily_pnl_eur":
                    daily_pnl,

                "consecutive_losses":
                    consecutive_losses,

                "trading_blocked":
                    trading_blocked,

                "block_reason":
                    block_reason,

                "updated_at":
                    now,
            }

            transaction.set(
                risk_ref,
                update,
                merge=True,
            )

            return update

        return record(
            transaction
        )

    # ========================================================
    # BLOCCO TRADING
    # ========================================================

    def block_trading(
        self,
        reason,
    ):

        self._risk_ref().set(
            {
                "trading_blocked":
                    True,

                "block_reason":
                    str(
                        reason
                    ),

                "updated_at":
                    self._now(),
            },
            merge=True,
        )

    def unblock_trading(
        self,
    ):

        self._risk_ref().set(
            {
                "trading_blocked":
                    False,

                "block_reason":
                    None,

                "updated_at":
                    self._now(),
            },
            merge=True,
        )

    # ========================================================
    # SIGNAL STATE
    # ========================================================

    def get_signal_state(
        self,
        symbol,
    ):

        snapshot = (
            self._signal_ref(
                symbol
            )
            .get()
        )

        if not snapshot.exists:
            return None

        data = (
            snapshot.to_dict()
        )

        if not data:
            return None

        return data

    def get_last_processed_candle(
        self,
        symbol,
    ):

        data = (
            self.get_signal_state(
                symbol
            )
        )

        if not data:
            return None

        return (
            data.get(
                "last_processed_candle"
            )
        )

    def is_candle_processed(
        self,
        symbol,
        candle_id,
    ):

        if candle_id is None:
            return False

        last_candle = (
            self.get_last_processed_candle(
                symbol
            )
        )

        return (
            str(last_candle)
            ==
            str(candle_id)
        )

    # ========================================================
    # CLAIM ATOMICO CANDELA M15
    # ========================================================

    def claim_signal_candle(
        self,
        symbol,
        candle_id,
        action=None,
    ):

        if candle_id is None:

            raise ValueError(
                "candle_id non può essere None"
            )

        symbol = (
            str(symbol)
            .upper()
            .strip()
        )

        candle_id = (
            str(
                candle_id
            )
        )

        document_ref = (
            self._signal_ref(
                symbol
            )
        )

        transaction = (
            self.db.transaction()
        )

        now = (
            self._now()
        )

        @firestore.transactional
        def claim(
            transaction,
        ):

            snapshot = (
                document_ref.get(
                    transaction=transaction
                )
            )

            if snapshot.exists:

                current = (
                    snapshot.to_dict()
                    or {}
                )

                last_candle = (
                    current.get(
                        "last_processed_candle"
                    )
                )

                if (
                    str(last_candle)
                    ==
                    candle_id
                ):

                    return False

            data = {

                "symbol":
                    symbol,

                "last_processed_candle":
                    candle_id,

                "last_action":
                    action,

                "processed_at":
                    now,

                "updated_at":
                    now,
            }

            transaction.set(
                document_ref,
                data,
                merge=True,
            )

            return True

        return claim(
            transaction
        )

    # ========================================================
    # RISULTATO ANALISI CANDELA
    # ========================================================

    def update_signal_result(
        self,
        symbol,
        candle_id,
        action,
        reason=None,
    ):

        data = {

            "last_processed_candle":
                str(
                    candle_id
                ),

            "last_action":
                action,

            "last_reason":
                reason,

            "updated_at":
                self._now(),
        }

        self._signal_ref(
            symbol
        ).set(
            data,
            merge=True,
        )

    # ========================================================
    # RESET SIGNAL STATE
    # Solo test / manutenzione.
    # ========================================================

    def clear_signal_state(
        self,
        symbol=None,
    ):

        if symbol is not None:

            self._signal_ref(
                symbol
            ).delete()

            return

        for symbol_name in (
            "BTC",
            "ETH",
        ):

            self._signal_ref(
                symbol_name
            ).delete()
