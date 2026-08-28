import os
import uuid
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

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
    # CREDENZIALI
    # ========================================================

    def _check_credentials(self):

        if not self.k.key or not self.k.secret:
            raise RuntimeError(
                "KRAKEN_API_KEY o KRAKEN_SECRET_KEY mancanti"
            )

    # ========================================================
    # CONTROLLO RISPOSTA KRAKEN
    # ========================================================

    @staticmethod
    def _check_response(response, operation):

        errors = response.get("error", [])

        if errors:
            raise RuntimeError(
                f"Kraken {operation} error: {errors}"
            )

        return response.get("result", {})

    # ========================================================
    # CLIENT ORDER ID
    # max 18 caratteri
    # ========================================================

    @staticmethod
    def _generate_client_order_id(order_type="e"):

        prefix_map = {
            "entry": "e",
            "stop": "s",
            "take_profit": "t",
        }

        prefix = prefix_map.get(
            order_type,
            str(order_type)[0].lower()
        )

        random_part = uuid.uuid4().hex[:13]

        return f"cb-{prefix}-{random_part}"

    # ========================================================
    # SALDO ACCOUNT
    # ========================================================

    def get_account_balance(self):

        self._check_credentials()

        response = self.k.query_private(
            "Balance"
        )

        result = self._check_response(
            response,
            "Balance"
        )

        return float(
            result.get(
                "ZEUR",
                result.get(
                    "EUR",
                    0.0
                )
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

        result = self._check_response(
            response,
            "OHLC"
        )

        data_keys = [
            key
            for key in result.keys()
            if key != "last"
        ]

        if not data_keys:
            return pd.DataFrame()

        raw = result[
            data_keys[0]
        ]

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

        # Kraken include normalmente anche
        # la candela ancora aperta.
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

        result = self._check_response(
            response,
            "Ticker"
        )

        if not result:
            raise RuntimeError(
                "Ticker Kraken non trovato"
            )

        key = next(
            iter(result.keys())
        )

        return float(
            result[key]["c"][0]
        )

    # ========================================================
    # INFORMAZIONI COPPIA
    # ========================================================

    def get_pair_info(self, pair):

        response = self.k.query_public(
            "AssetPairs",
            {
                "pair": pair
            }
        )

        result = self._check_response(
            response,
            "AssetPairs"
        )

        if not result:
            raise RuntimeError(
                f"Coppia Kraken non trovata: {pair}"
            )

        # Normalmente Kraken restituisce
        # una sola coppia perché l'abbiamo richiesta.
        pair_key = next(
            iter(result.keys())
        )

        info = result[pair_key]

        return {
            "key": pair_key,
            "altname": info.get(
                "altname",
                pair
            ),
            "wsname": info.get(
                "wsname"
            ),
            "base": info.get(
                "base"
            ),
            "quote": info.get(
                "quote"
            ),
            "pair_decimals": int(
                info.get(
                    "pair_decimals",
                    8
                )
            ),
            "lot_decimals": int(
                info.get(
                    "lot_decimals",
                    8
                )
            ),
            "ordermin": float(
                info.get(
                    "ordermin",
                    0
                )
            ),
            "costmin": float(
                info.get(
                    "costmin",
                    0
                )
            ),
            "tick_size": float(
                info.get(
                    "tick_size",
                    0
                )
            ),
            "leverage_buy": [
                float(x)
                for x in info.get(
                    "leverage_buy",
                    []
                )
            ],
            "leverage_sell": [
                float(x)
                for x in info.get(
                    "leverage_sell",
                    []
                )
            ],
            "status": info.get(
                "status",
                "unknown"
            ),
        }

    # ========================================================
    # FORMATTA QUANTITÀ
    # ========================================================

    def format_volume(
        self,
        pair,
        volume
    ):

        pair_info = self.get_pair_info(
            pair
        )

        decimals = pair_info[
            "lot_decimals"
        ]

        quantum = Decimal(
            "1"
        ).scaleb(
            -decimals
        )

        value = Decimal(
            str(volume)
        )

        rounded = value.quantize(
            quantum,
            rounding=ROUND_DOWN
        )

        return format(
            rounded,
            "f"
        )

    # ========================================================
    # FORMATTA PREZZO
    # ========================================================

    def format_price(
        self,
        pair,
        price
    ):

        pair_info = self.get_pair_info(
            pair
        )

        tick_size = pair_info.get(
            "tick_size",
            0
        )

        value = Decimal(
            str(price)
        )

        if tick_size and tick_size > 0:

            tick = Decimal(
                str(tick_size)
            )

            ticks = (
                value / tick
            ).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )

            rounded = (
                ticks * tick
            )

            return format(
                rounded,
                "f"
            )

        decimals = pair_info[
            "pair_decimals"
        ]

        quantum = Decimal(
            "1"
        ).scaleb(
            -decimals
        )

        rounded = value.quantize(
            quantum,
            rounding=ROUND_HALF_UP
        )

        return format(
            rounded,
            "f"
        )

    # ========================================================
    # VALIDAZIONE QUANTITÀ / MINIMO
    # ========================================================

    def validate_order_size(
        self,
        pair,
        volume,
        price
    ):

        info = self.get_pair_info(
            pair
        )

        formatted_volume = (
            self.format_volume(
                pair,
                volume
            )
        )

        numeric_volume = float(
            formatted_volume
        )

        notional = (
            numeric_volume
            * float(price)
        )

        ordermin = info[
            "ordermin"
        ]

        costmin = info[
            "costmin"
        ]

        if numeric_volume <= 0:
            raise RuntimeError(
                "Quantità ordine pari a zero "
                "dopo l'arrotondamento Kraken"
            )

        if (
            ordermin > 0
            and numeric_volume < ordermin
        ):
            raise RuntimeError(
                f"Quantità {numeric_volume} "
                f"inferiore al minimo Kraken "
                f"{ordermin}"
            )

        if (
            costmin > 0
            and notional < costmin
        ):
            raise RuntimeError(
                f"Controvalore {notional:.2f} "
                f"inferiore al minimo Kraken "
                f"{costmin:.2f}"
            )

        return {
            "allowed": True,
            "volume": formatted_volume,
            "notional": notional,
            "ordermin": ordermin,
            "costmin": costmin,
            "pair_info": info,
        }

    # ========================================================
    # CONTROLLO LEVA
    # ========================================================

    def validate_leverage(
        self,
        pair,
        side,
        leverage
    ):

        if (
            leverage is None
            or float(leverage) <= 1
        ):
            return None

        info = self.get_pair_info(
            pair
        )

        if side.lower() == "buy":
            available = info[
                "leverage_buy"
            ]
        else:
            available = info[
                "leverage_sell"
            ]

        requested = float(
            leverage
        )

        if requested not in available:

            raise RuntimeError(
                f"Leva {requested}x non disponibile "
                f"per {pair} {side}. "
                f"Leve Kraken disponibili: "
                f"{available}"
            )

        # Kraken normalmente usa valori
        # interi per queste coppie.
        if requested.is_integer():
            return str(
                int(requested)
            )

        return str(
            requested
        )

    # ========================================================
    # ORDINI APERTI
    # ========================================================

    def get_open_orders(self):

        self._check_credentials()

        response = self.k.query_private(
            "OpenOrders"
        )

        result = self._check_response(
            response,
            "OpenOrders"
        )

        return result.get(
            "open",
            {}
        )

    # ========================================================
    # ORDINI CHIUSI
    # ========================================================

    def get_closed_orders(self):

        self._check_credentials()

        response = self.k.query_private(
            "ClosedOrders"
        )

        result = self._check_response(
            response,
            "ClosedOrders"
        )

        return result.get(
            "closed",
            {}
        )

    # ========================================================
    # DETTAGLIO ORDINE
    # ========================================================

    def get_order_info(self, txid):

        self._check_credentials()

        response = self.k.query_private(
            "QueryOrders",
            {
                "txid": txid,
                "trades": True
            }
        )

        result = self._check_response(
            response,
            "QueryOrders"
        )

        return result.get(
            txid,
            {}
        )

    # ========================================================
    # POSIZIONI APERTE
    # ========================================================

    def get_open_positions(self):

        self._check_credentials()

        response = self.k.query_private(
            "OpenPositions"
        )

        result = self._check_response(
            response,
            "OpenPositions"
        )

        return result

    # ========================================================
    # ORDINE MARKET
    # ========================================================

    def create_market_order(
        self,
        pair,
        side,
        volume,
        leverage=None,
        validate=False,
        client_order_id=None
    ):

        self._check_credentials()

        side = side.lower()

        if side not in (
            "buy",
            "sell"
        ):
            raise ValueError(
                "side deve essere BUY o SELL"
            )

        current_price = self.get_ticker(
            pair
        )

        size_check = (
            self.validate_order_size(
                pair=pair,
                volume=volume,
                price=current_price
            )
        )

        formatted_volume = (
            size_check["volume"]
        )

        if client_order_id is None:
            client_order_id = (
                self._generate_client_order_id(
                    "entry"
                )
            )

        data = {
            "pair": pair,
            "type": side,
            "ordertype": "market",
            "volume": formatted_volume,
            "cl_ord_id": client_order_id,
            "validate": bool(validate),
        }

        formatted_leverage = (
            self.validate_leverage(
                pair=pair,
                side=side,
                leverage=leverage
            )
        )

        if formatted_leverage:
            data[
                "leverage"
            ] = formatted_leverage

        safe_log = {
            "pair": pair,
            "type": side,
            "ordertype": "market",
            "volume": formatted_volume,
            "leverage": formatted_leverage,
            "validate": bool(validate),
            "cl_ord_id": client_order_id,
        }

        print(
            f"Ordine Kraken: {safe_log}"
        )

        response = self.k.query_private(
            "AddOrder",
            data
        )

        result = self._check_response(
            response,
            "AddOrder"
        )

        return result

    # ========================================================
    # STOP LOSS
    # ========================================================

    def create_stop_loss_order(
        self,
        pair,
        entry_side,
        volume,
        stop_price,
        leverage=None,
        validate=False,
        reduce_only=True,
        client_order_id=None
    ):

        self._check_credentials()

        entry_side = (
            entry_side.lower()
        )

        if entry_side == "buy":
            exit_side = "sell"

        elif entry_side == "sell":
            exit_side = "buy"

        else:
            raise ValueError(
                "entry_side deve essere BUY o SELL"
            )

        formatted_volume = (
            self.format_volume(
                pair,
                volume
            )
        )

        formatted_price = (
            self.format_price(
                pair,
                stop_price
            )
        )

        if client_order_id is None:
            client_order_id = (
                self._generate_client_order_id(
                    "stop"
                )
            )

        data = {
            "pair": pair,
            "type": exit_side,
            "ordertype": "stop-loss",
            "volume": formatted_volume,
            "price": formatted_price,
            "cl_ord_id": client_order_id,
            "validate": bool(validate),
        }

        formatted_leverage = (
            self.validate_leverage(
                pair=pair,
                side=exit_side,
                leverage=leverage
            )
        )

        if formatted_leverage:
            data[
                "leverage"
            ] = formatted_leverage

            if reduce_only:
                data[
                    "reduce_only"
                ] = True

        print(
            "Invio Stop Loss Kraken: "
            f"{data}"
        )

        response = self.k.query_private(
            "AddOrder",
            data
        )

        result = self._check_response(
            response,
            "AddOrder Stop Loss"
        )

        return result

    # ========================================================
    # TAKE PROFIT
    # ========================================================

    def create_take_profit_order(
        self,
        pair,
        entry_side,
        volume,
        take_profit_price,
        leverage=None,
        validate=False,
        reduce_only=True,
        client_order_id=None
    ):

        self._check_credentials()

        entry_side = (
            entry_side.lower()
        )

        if entry_side == "buy":
            exit_side = "sell"

        elif entry_side == "sell":
            exit_side = "buy"

        else:
            raise ValueError(
                "entry_side deve essere BUY o SELL"
            )

        formatted_volume = (
            self.format_volume(
                pair,
                volume
            )
        )

        formatted_price = (
            self.format_price(
                pair,
                take_profit_price
            )
        )

        if client_order_id is None:
            client_order_id = (
                self._generate_client_order_id(
                    "take_profit"
                )
            )

        data = {
            "pair": pair,
            "type": exit_side,
            "ordertype": "take-profit",
            "volume": formatted_volume,
            "price": formatted_price,
            "cl_ord_id": client_order_id,
            "validate": bool(validate),
        }

        formatted_leverage = (
            self.validate_leverage(
                pair=pair,
                side=exit_side,
                leverage=leverage
            )
        )

        if formatted_leverage:
            data[
                "leverage"
            ] = formatted_leverage

            if reduce_only:
                data[
                    "reduce_only"
                ] = True

        print(
            "Invio Take Profit Kraken: "
            f"{data}"
        )

        response = self.k.query_private(
            "AddOrder",
            data
        )

        result = self._check_response(
            response,
            "AddOrder Take Profit"
        )

        return result
    # ========================================================
    # CHIUSURA DI EMERGENZA A MERCATO
    # ========================================================

    def close_position_market(
        self,
        pair,
        entry_side,
        volume,
        leverage=None,
        validate=False,
        client_order_id=None
    ):
        """
        Chiude una posizione esistente a mercato.

        BUY aperto  -> SELL di chiusura
        SELL aperto -> BUY di chiusura

        reduce_only=True impedisce all'ordine
        di aumentare o invertire la posizione.
        """

        self._check_credentials()

        entry_side = entry_side.lower()

        if entry_side == "buy":
            exit_side = "sell"

        elif entry_side == "sell":
            exit_side = "buy"

        else:
            raise ValueError(
                "entry_side deve essere BUY o SELL"
            )

        current_price = self.get_ticker(
            pair
        )

        size_check = self.validate_order_size(
            pair=pair,
            volume=volume,
            price=current_price
        )

        formatted_volume = size_check[
            "volume"
        ]

        if client_order_id is None:
            client_order_id = (
                self._generate_client_order_id(
                    "emergency"
                )
            )

        data = {
            "pair": pair,
            "type": exit_side,
            "ordertype": "market",
            "volume": formatted_volume,
            "reduce_only": True,
            "cl_ord_id": client_order_id,
            "validate": bool(validate),
        }

        formatted_leverage = (
            self.validate_leverage(
                pair=pair,
                side=exit_side,
                leverage=leverage
            )
        )

        if formatted_leverage:
            data[
                "leverage"
            ] = formatted_leverage

        safe_log = {
            "pair": pair,
            "type": exit_side,
            "ordertype": "market",
            "volume": formatted_volume,
            "reduce_only": True,
            "leverage": formatted_leverage,
            "validate": bool(validate),
            "cl_ord_id": client_order_id,
        }

        print(
            "CHIUSURA EMERGENZA KRAKEN: "
            f"{safe_log}"
        )

        response = self.k.query_private(
            "AddOrder",
            data
        )

        result = self._check_response(
            response,
            "Emergency Close"
        )

        return result
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

        return self._check_response(
            response,
            "CancelOrder"
        )

    # ========================================================
    # TEST CONNESSIONE
    # ========================================================

    def test_connection(self):

        balance = (
            self.get_account_balance()
        )

        return {
            "connected": True,
            "balance_eur": balance
        }
