import os
import time

import pandas as pd
import krakenex
from dotenv import load_dotenv

load_dotenv()


class KrakenClient:

    def __init__(self):

        self.k = krakenex.API()

        self.k.key = os.getenv(
            "KRAKEN_API_KEY",
            ""
        ).strip()

        self.k.secret = os.getenv(
            "KRAKEN_SECRET_KEY",
            ""
        ).strip()


    # ========================================================
    # GENERIC REQUEST
    # ========================================================

    def _check_credentials(self):

        if not self.k.key or not self.k.secret:

            raise RuntimeError(
                "KRAKEN_API_KEY o KRAKEN_SECRET_KEY mancanti"
            )


    # ========================================================
    # BALANCE
    # ========================================================

    def get_account_balance(self):

        self._check_credentials()

        response = self.k.query_private(
            "Balance"
        )

        if response.get("error"):

            raise RuntimeError(
                f"Kraken Balance error: "
                f"{response['error']}"
            )

        balances = response.get(
            "result",
            {}
        )

        return float(
            balances.get(
                "ZEUR",
                balances.get("EUR", 0.0)
            )
        )


    # ========================================================
    # OHLC
    # ========================================================

    def get_ohlc(
        self,
        pair,
        interval
    ):

        response = self.k.query_public(
            "OHLC",
            {
                "pair": pair,
                "interval": interval
            }
        )

        if response.get("error"):

            raise RuntimeError(
                f"Kraken OHLC error: "
                f"{response['error']}"
            )

        result = response.get(
            "result",
            {}
        )

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

        numeric = [
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
        ]

        for column in numeric:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df["time"] = pd.to_datetime(
            df["time"],
            unit="s",
            utc=True
        )

        # Eliminiamo l'ultima candela perché
        # può essere ancora in formazione.
        if len(df) > 1:

            df = df.iloc[:-1].copy()

        return df


    # ========================================================
    # OPEN ORDERS
    # ========================================================

    def get_open_orders(self):

        self._check_credentials()

        response = self.k.query_private(
            "OpenOrders"
        )

        if response.get("error"):

            raise RuntimeError(
                f"Kraken OpenOrders error: "
                f"{response['error']}"
            )

        return response.get(
            "result",
            {}
        ).get(
            "open",
            {}
        )


    # ========================================================
    # OPEN POSITIONS
    # ========================================================

    def get_open_positions(self):

        self._check_credentials()

        response = self.k.query_private(
            "OpenPositions"
        )

        if response.get("error"):

            raise RuntimeError(
                f"Kraken OpenPositions error: "
                f"{response['error']}"
            )

        return response.get(
            "result",
            {}
        )


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
                f"Kraken Ticker error: "
                f"{response['error']}"
            )

        result = response.get(
            "result",
            {}
        )

        key = next(
            (
                x
                for x in result.keys()
                if x != "last"
            ),
            None
        )

        if not key:

            raise RuntimeError(
                "Ticker Kraken non trovato"
            )

        return float(
            result[key]["c"][0]
        )


    # ========================================================
    # MARKET ORDER
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

            data["leverage"] = str(
                leverage
            )

        print(
            f"📤 ORDINE KRAKEN: {data}"
        )

        response = self.k.query_private(
            "AddOrder",
            data
        )

        if response.get("error"):

            raise RuntimeError(
                f"Kraken AddOrder error: "
                f"{response['error']}"
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
                f"Kraken CancelOrder error: "
                f"{response['error']}"
            )

        return response


    # ========================================================
    # API KEY TEST
    # ========================================================

    def test_connection(self):

        balance = self.get_account_balance()

        return {
            "connected": True,
            "balance_eur": balance
        }
