import os
import krakenex
from dotenv import load_dotenv

# Carica il file .env
load_dotenv()

api_key = os.getenv("KRAKEN_API_KEY", "").strip()
api_secret = os.getenv("KRAKEN_SECRET_KEY", "").strip()

print("--- DEBUG VARIABILI D'AMBIENTE ---")
print(f"Lunghezza API Key: {len(api_key)} caratteri")
print(f"Lunghezza Secret Key: {len(api_secret)} caratteri")

# Inizializza l'SDK Ufficiale Kraken
k = krakenex.API()
k.key = api_key
k.secret = api_secret

print("\n--- TEST CONNETTIVITÀ API ---")
try:
    # Chiamata di test al saldo
    response = k.query_private('Balance')
    print("Risposta grezza da Kraken:")
    print(response)

    if response.get('error'):
        print(f"\n❌ Errore restituito da Kraken: {response['error']}")
    else:
        print("\n✅ CONNESSI CON SUCCESSO!")
        print("Dati saldo:", response.get('result'))

except Exception as e:
    print(f"\n❌ Eccezione durante la chiamata: {e}")
