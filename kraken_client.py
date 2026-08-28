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

    def get_account_balance(self):
        """Recupera il saldo in Euro disponibile"""
        if not self.k.key or not self.k.secret:
            print("⚠️ Errore: KRAKEN_API_KEY o KRAKEN_SECRET_KEY mancanti nel file .env")
            return 0.0

        try:
            res = self.k.query_private('Balance')
            if res.get('error'):
                print(f"⚠️ Errore API Kraken: {res['error']}")
                return 0.0

            balances = res.get('result', {})
            eur_val = float(balances.get('ZEUR', balances.get('EUR', 0.0)))
            return eur_val

        except Exception as e:
            print(f"⚠️ Errore di connessione a Kraken: {e}")
            return 0.0

    def get_crypto_balance(self, asset="XXBT"):
        """Recupera il saldo di una specifica criptovaluta"""
        try:
            res = self.k.query_private('Balance')
            if res.get('error'):
                return 0.0
            balances = res.get('result', {})
            return float(balances.get(asset, 0.0))
        except Exception:
            return 0.0

    def get_daily_ohlc(self, pair="XXBTZEUR", interval=1440):
        """Scarica i dati storici delle candele (OHLC) per l'analisi tecnica"""
        try:
            res = self.k.query_public('OHLC', {'pair': pair, 'interval': interval})
            if res.get('error'):
                print(f"⚠️ Errore recupero dati OHLC per {pair}: {res['error']}")
                return pd.DataFrame()

            result = res.get('result', {})
            data_key = [k for k in result.keys() if k != 'last']
            if not data_key:
                return pd.DataFrame()

            raw_data = result[data_key[0]]
            
            df = pd.DataFrame(raw_data, columns=[
                'time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'
            ])
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df

        except Exception as e:
            print(f"⚠️ Errore durante il download dei dati OHLC: {e}")
            return pd.DataFrame()

if __name__ == "__main__":
    client = KrakenClient()
    saldo = client.get_account_balance()
    print(f"💰 Saldo confermato: {saldo:.2f} EUR")
