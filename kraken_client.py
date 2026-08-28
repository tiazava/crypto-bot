import os

import pandas as pd
import krakenex
from dotenv import load_dotenv

load_dotenv()


class KrakenClient:

    def __init__(self):
        self.k = krakenex.API()
        self.k.key = os.getenv("KRAKEN_API_KEY", "").strip()
        self.k.secret = os.getenv("KRAKEN_SECRET_KEY", "").strip()

    def _check_credentials(self):
        if not self.k.key or not self.k.secret:
            raise RuntimeError(
                "KRAKEN_API_KEY o KRAKEN_SECRET_KEY mancanti"
            )

    # ========================================================
    # SALDO ACCOUNT
    # ========================================================

    def get_account_balance(self):
        self._check_credentials()

        response = self.k.query_private("Balance")

        if response.get("error"):
            raise RuntimeError(
                f"Kraken Balance error: {response['error']}"
            )

        balances = response.get("result", {})

        return float(
            balances.get(
                "ZEUR",
                balances.get("EUR", 0.0)
            )
        )

    # ========================================================
    # OHLC
    # ========================================================

    def get_ohlc(self, pair, interval):
        response = self.k.query_public(
            "OHLC",
            {
                "pair": pair,
                "interval": interval
            }
        )

        if response.get("error"):
            raise RuntimeError(
                f"Kraken OHLC error: {response['error']}"
            )

        result = response.get("result", {})

        data_keys = [
            key
            for key in result.keys()
            if key != "last"
        ]

        if not data_keys:
            return pd.DataFrame()

        raw = result[data_keys[0]]

        df = pd.DataFrame(
            raw,
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "vwap",
                "volume",
                "count",
            ]
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df["time"] = pd.to_datetime(
            df["time"],
            unit="s",
            utc=True
        )

        # L'ultima candela Kraken può essere ancora aperta.
        # La eliminiamo per non prendere segnali incompleti.
        if len(df) > 1:
            df = df.iloc[:-1].copy()

        return df

    # ========================================================
    # TICKER
    # ========================================================

    def get_ticker(self, pair):
        response = self.k.query_public(
            "Ticker",
            {
                "pair": pair
            }
        )

        if response.get("error"):
            raise RuntimeError(
                f"Kraken Ticker error: {response['error']}"
            )

        result = response.get("result", {})

        if not result:
            raise RuntimeError(
                "Ticker Kraken non trovato"
            )

        key = next(iter(result.keys()))

        return float(
            result[key]["c"][0]
        )

    # ========================================================
    # ORDINI APERTI
    # ========================================================

    def get_open_orders(self):
        self._check_credentials()

        response = self.k.query_private(
            "OpenOrders"
        )

        if response.get("error"):
            raise RuntimeError(
                f"Kraken OpenOrders error: {response['error']}"
            )

        return (
            response
            .get("result", {})
            .get("open", {})
        )

    # ========================================================
    # POSIZIONI APERTE
    # ========================================================

    def get_open_positions(self):
        self._check_credentials()

        response = self.k.query_private(
            "OpenPositions"
        )

        if response.get("error"):
            raise RuntimeError(
                f"Kraken OpenPositions error: {response['error']}"
            )

        return response.get(
            "result",
            {}
        )

    # ========================================================
    # ORDINE MARKET
    # ========================================================

    def create_market_order(
        self,
        pair,
        side,
        volume,
        leverage=None
    ):
        self._check_credentials()

        data = {
            "pair": pair,
            "type": side.lower(),
            "ordertype": "market",
            "volume": f"{volume:.8f}",
        }

        if leverage and leverage > 1:
            data["leverage"] = str(leverage)

        print(
            f"Invio ordine Kraken: {data}"
        )

        response = self.k.query_private(
            "AddOrder",
            data
        )

        if response.get("error"):
            raise RuntimeError(
                f"Kraken AddOrder error: {response['error']}"
            )

        return response.get(
            "result",
            {}
        )

    # ========================================================
    # CANCEL ORDER
    # ========================================================

    def cancel_order(self, txid):
        self._check_credentials()

        response = self.k.query_private(
            "CancelOrder",
            {
                "txid": txid
            }
        )

        if response.get("error"):
            raise RuntimeError(
                f"Kraken CancelOrder error: {response['error']}"
            )

        return response

    # ========================================================
    # TEST CONNESSIONE
    # ========================================================

    def test_connection(self):
        balance = self.get_account_balance()

        return {
            "connected": True,
            "balance_eur": balance
        }
