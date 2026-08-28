from datetime import datetime, timezone

from google.cloud import firestore


COLLECTION_NAME = "trade_state"
ACTIVE_TRADE_DOCUMENT_ID = "active_trade"
RISK_DOCUMENT_ID = "risk_state"


class TradeState:

    def __init__(self):
        self.db = firestore.Client()

    # ========================================================
    # UTILITÀ
    # ========================================================

    def _now(self):
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _today(self):
        return datetime.now(
            timezone.utc
        ).date().isoformat()

    def _trade_ref(self):
        return (
            self.db
            .collection(COLLECTION_NAME)
            .document(ACTIVE_TRADE_DOCUMENT_ID)
        )

    def _risk_ref(self):
        return (
            self.db
            .collection(COLLECTION_NAME)
            .document(RISK_DOCUMENT_ID)
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

        data = snapshot.to_dict()

        if not data:
            return None

        return data

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

            "signal_candle": signal_candle,

            "close_reason": None,
            "exit_price": None,
            "pnl_eur": None,

            "telegram_open_sent": False,
            "telegram_close_sent": False,

            "created_at": now,
            "updated_at": now,
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

        self._trade_ref().update(
            update
        )

    def mark_entry_filled(
        self,
        fill_price,
        filled_volume
    ):

        self._trade_ref().update(
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
    # PROTEZIONI
    # ========================================================

    def mark_protection_pending(self):

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

        self._trade_ref().update(
            update
        )

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

        self._trade_ref().update(
            update
        )

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

        now = self._now()

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
    # USCITA
    # ========================================================

    def mark_exit_pending(
        self,
        close_reason
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

    def close_trade(
        self,
        close_reason,
        exit_price=None,
        pnl_eur=None,
    ):

        now = self._now()

        update = {
            "status": "CLOSED",
            "close_reason": close_reason,
            "closed_at": now,
            "updated_at": now,
        }

        if exit_price is not None:
            update[
                "exit_price"
            ] = float(exit_price)

        if pnl_eur is not None:
            update[
                "pnl_eur"
            ] = float(pnl_eur)

        self._trade_ref().update(
            update
        )

        # Aggiorna automaticamente
        # i limiti di rischio quando
        # conosciamo il P&L reale.
        if pnl_eur is not None:
            self.record_trade_result(
                float(pnl_eur)
            )

    # ========================================================
    # TELEGRAM
    # ========================================================

    def mark_telegram_open_sent(self):

        self._trade_ref().update(
            {
                "telegram_open_sent":
                    True,

                "updated_at":
                    self._now(),
            }
        )

    def mark_telegram_close_sent(self):

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
        message
    ):

        self._trade_ref().update(
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
    # CANCELLAZIONE STATO TRADE
    # ========================================================

    def clear_trade(self):

        self._trade_ref().delete()

    # ========================================================
    # RISK STATE
    # ========================================================

    def _default_risk_state(self):

        now = self._now()

        return {
            "date": self._today(),
            "daily_pnl_eur": 0.0,
            "consecutive_losses": 0,
            "trading_blocked": False,
            "block_reason": None,
            "updated_at": now,
        }

    def get_risk_state(self):

        snapshot = (
            self._risk_ref()
            .get()
        )

        if not snapshot.exists:

            data = (
                self._default_risk_state()
            )

            self._risk_ref().set(
                data
            )

            return data

        data = snapshot.to_dict()

        if not data:

            data = (
                self._default_risk_state()
            )

            self._risk_ref().set(
                data
            )

            return data

        # Se è iniziato un nuovo giorno,
        # resettiamo solo il P&L giornaliero
        # e l'eventuale blocco giornaliero.
        if data.get("date") != self._today():

            consecutive_losses = int(
                data.get(
                    "consecutive_losses",
                    0
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

            self._risk_ref().set(
                data
            )

        return data

    # ========================================================
    # REGISTRA RISULTATO TRADE
    # ========================================================

    def record_trade_result(
        self,
        pnl_eur
    ):

        risk = self.get_risk_state()

        pnl_eur = float(
            pnl_eur
        )

        daily_pnl = float(
            risk.get(
                "daily_pnl_eur",
                0.0
            )
        )

        daily_pnl += pnl_eur

        consecutive_losses = int(
            risk.get(
                "consecutive_losses",
                0
            )
        )

        if pnl_eur < 0:

            consecutive_losses += 1

        else:

            consecutive_losses = 0

        update = {
            "date":
                self._today(),

            "daily_pnl_eur":
                daily_pnl,

            "consecutive_losses":
                consecutive_losses,

            "updated_at":
                self._now(),
        }

        self._risk_ref().set(
            update,
            merge=True
        )

        return {
            **risk,
            **update,
        }

    # ========================================================
    # BLOCCO MANUALE/AUTOMATICO
    # ========================================================

    def block_trading(
        self,
        reason
    ):

        self._risk_ref().set(
            {
                "trading_blocked":
                    True,

                "block_reason":
                    str(reason),

                "updated_at":
                    self._now(),
            },
            merge=True
        )

    def unblock_trading(self):

        self._risk_ref().set(
            {
                "trading_blocked":
                    False,

                "block_reason":
                    None,

                "updated_at":
                    self._now(),
            },
            merge=True
        )
