from datetime import datetime, timezone

from google.cloud import firestore


COLLECTION_NAME = "trade_state"
DOCUMENT_ID = "active_trade"


class TradeState:

    def __init__(self):
        self.db = firestore.Client()

    def _doc_ref(self):
        return (
            self.db
            .collection(COLLECTION_NAME)
            .document(DOCUMENT_ID)
        )

    def _now(self):
        return datetime.now(
            timezone.utc
        ).isoformat()

    # ========================================================
    # LETTURA STATO
    # ========================================================

    def get_trade(self):

        snapshot = (
            self._doc_ref()
            .get()
        )

        if not snapshot.exists:
            return None

        data = snapshot.to_dict()

        if not data:
            return None

        return data

    # ========================================================
    # TRADE ATTIVO
    # ========================================================

    def get_active_trade(self):

        trade = self.get_trade()

        if not trade:
            return None

        active_statuses = {
            "ENTRY_PENDING",
            "ENTRY_FILLED",
            "PROTECTION_PENDING",
            "PROTECTED",
            "EXIT_PENDING",
        }

        if trade.get("status") not in active_statuses:
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

        now = self._now()

        data = {
            "status": "ENTRY_PENDING",
            "symbol": symbol,
            "pair": pair,
            "side": side.upper(),

            "requested_entry_price": float(
                requested_entry_price
            ),

            "requested_volume": float(
                requested_volume
            ),

            "stop_loss": float(
                stop_loss
            ),

            "take_profit": float(
                take_profit
            ),

            "leverage": float(
                leverage
            ),

            "entry_client_order_id":
                entry_client_order_id,

            "entry_txid": None,
            "entry_fill_price": None,
            "entry_filled_volume": None,

            "stop_client_order_id": None,
            "stop_txid": None,

            "take_profit_client_order_id": None,
            "take_profit_txid": None,

            "signal_candle":
                signal_candle,

            "close_reason": None,
            "exit_price": None,
            "pnl_eur": None,

            "telegram_open_sent": False,
            "telegram_close_sent": False,

            "created_at": now,
            "updated_at": now,
        }

        self._doc_ref().set(
            data
        )

        return data

    # ========================================================
    # ENTRY INVIATA
    # ========================================================

    def set_entry_order(
        self,
        txid,
        client_order_id=None
    ):

        update = {
            "entry_txid": txid,
            "updated_at": self._now(),
        }

        if client_order_id:
            update[
                "entry_client_order_id"
            ] = client_order_id

        self._doc_ref().update(
            update
        )

    # ========================================================
    # ENTRY ESEGUITA
    # ========================================================

    def mark_entry_filled(
        self,
        fill_price,
        filled_volume
    ):

        self._doc_ref().update(
            {
                "status": "ENTRY_FILLED",

                "entry_fill_price":
                    float(fill_price),

                "entry_filled_volume":
                    float(filled_volume),

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # PROTEZIONI IN PREPARAZIONE
    # ========================================================

    def mark_protection_pending(self):

        self._doc_ref().update(
            {
                "status":
                    "PROTECTION_PENDING",

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # STOP LOSS
    # ========================================================

    def set_stop_order(
        self,
        txid,
        client_order_id=None
    ):

        update = {
            "stop_txid": txid,
            "updated_at": self._now(),
        }

        if client_order_id:
            update[
                "stop_client_order_id"
            ] = client_order_id

        self._doc_ref().update(
            update
        )

    # ========================================================
    # TAKE PROFIT
    # ========================================================

    def set_take_profit_order(
        self,
        txid,
        client_order_id=None
    ):

        update = {
            "take_profit_txid": txid,
            "updated_at": self._now(),
        }

        if client_order_id:
            update[
                "take_profit_client_order_id"
            ] = client_order_id

        self._doc_ref().update(
            update
        )

    # ========================================================
    # TRADE PROTETTO
    # ========================================================

    def mark_protected(self):

        trade = self.get_trade()

        if not trade:
            raise RuntimeError(
                "Nessun trade Firestore presente"
            )

        if not trade.get("stop_txid"):
            raise RuntimeError(
                "Stop Loss non presente"
            )

        if not trade.get(
            "take_profit_txid"
        ):
            raise RuntimeError(
                "Take Profit non presente"
            )

        self._doc_ref().update(
            {
                "status":
                    "PROTECTED",

                "protected_at":
                    self._now(),

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # USCITA IN CORSO
    # ========================================================

    def mark_exit_pending(
        self,
        close_reason
    ):

        self._doc_ref().update(
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
    # CHIUSURA TRADE
    # ========================================================

    def close_trade(
        self,
        close_reason,
        exit_price=None,
        pnl_eur=None,
    ):

        now = self._now()

        update = {
            "status": "CLOSED",
            "close_reason":
                close_reason,

            "closed_at":
                now,

            "updated_at":
                now,
        }

        if exit_price is not None:
            update[
                "exit_price"
            ] = float(exit_price)

        if pnl_eur is not None:
            update[
                "pnl_eur"
            ] = float(pnl_eur)

        self._doc_ref().update(
            update
        )

    # ========================================================
    # TELEGRAM
    # ========================================================

    def mark_telegram_open_sent(self):

        self._doc_ref().update(
            {
                "telegram_open_sent":
                    True,

                "updated_at":
                    self._now(),
            }
        )

    def mark_telegram_close_sent(self):

        self._doc_ref().update(
            {
                "telegram_close_sent":
                    True,

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # ERRORE
    # ========================================================

    def mark_error(
        self,
        message
    ):

        self._doc_ref().update(
            {
                "status":
                    "ERROR",

                "error_message":
                    str(message),

                "updated_at":
                    self._now(),
            }
        )

    # ========================================================
    # CANCELLAZIONE STATO
    # ========================================================

    def clear_trade(self):

        self._doc_ref().delete()
