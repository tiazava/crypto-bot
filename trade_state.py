from datetime import datetime, timezone

from google.cloud import firestore


COLLECTION_NAME = "trade_state"
DOCUMENT_ID = "active_trade"


class TradeState:

    def __init__(self):
        self.db = firestore.Client()

    def get_active_trade(self):
        doc_ref = (
            self.db
            .collection(COLLECTION_NAME)
            .document(DOCUMENT_ID)
        )

        snapshot = doc_ref.get()

        if not snapshot.exists:
            return None

        data = snapshot.to_dict()

        if not data:
            return None

        if data.get("status") != "OPEN":
            return None

        return data

    def save_active_trade(
        self,
        symbol,
        pair,
        side,
        entry_price,
        volume,
        stop_loss,
        take_profit,
        entry_txid,
        stop_txid,
        take_profit_txid,
    ):
        now = datetime.now(
            timezone.utc
        ).isoformat()

        data = {
            "status": "OPEN",
            "symbol": symbol,
            "pair": pair,
            "side": side,
            "entry_price": float(entry_price),
            "volume": float(volume),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "entry_txid": entry_txid,
            "stop_txid": stop_txid,
            "take_profit_txid": take_profit_txid,
            "opened_at": now,
            "updated_at": now,
        }

        (
            self.db
            .collection(COLLECTION_NAME)
            .document(DOCUMENT_ID)
            .set(data)
        )

        return data

    def close_trade(
        self,
        close_reason,
        exit_price=None,
        pnl_eur=None,
    ):
        now = datetime.now(
            timezone.utc
        ).isoformat()

        update_data = {
            "status": "CLOSED",
            "close_reason": close_reason,
            "closed_at": now,
            "updated_at": now,
        }

        if exit_price is not None:
            update_data[
                "exit_price"
            ] = float(exit_price)

        if pnl_eur is not None:
            update_data[
                "pnl_eur"
            ] = float(pnl_eur)

        (
            self.db
            .collection(COLLECTION_NAME)
            .document(DOCUMENT_ID)
            .update(update_data)
        )

    def clear_trade(self):
        (
            self.db
            .collection(COLLECTION_NAME)
            .document(DOCUMENT_ID)
            .delete()
        )
