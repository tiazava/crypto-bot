from datetime import datetime
from kraken_client import KrakenClient
from strategy import analyze_market
from anthropic_guard import AnthropicGuard
from config import PAIRS

def run():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 Avvio Scansione Trading & News AI Guard...")
    
    kraken = KrakenClient()
    
    # Recupera il saldo reale del conto Kraken
    balance = kraken.get_account_balance()
    print(f"💰 Capitale Operativo Disponibile: {balance:.2f} EUR")

    guard = AnthropicGuard()

    for symbol, pair_code in PAIRS.items():
        print(f"\n==================================================")
        print(f"📈 Analisi Tecnica per {symbol} ({pair_code})...")
        print(f"==================================================")
        
        ohlc = kraken.get_daily_ohlc(pair_code)
        if ohlc.empty:
            continue
            
        analysis = analyze_market(ohlc)
        
        if analysis['action'] == 'BUY':
            print(f"🚨 SEGNALE TECNICO RILEVATO per {symbol}!")
            print(f"🔹 Prezzo Attuale: {analysis['price']:.2f} EUR | RSI: {analysis['rsi']} | Leva Proposta: {analysis['leverage']}x")
            
            print(f"🔍 Verifica Notizie e Sentiment via AI Guard...")
            approved, reason = guard.check_news_sentiment(symbol)
            
            if approved:
                print(f"✅ AI Guard: OPERAZIONE APPROVATA -> {reason}")
                
                if balance > 0:
                    print(f"🛒 Invio ordine su Kraken con saldo reale ({balance:.2f} EUR)...")
                else:
                    print(f"⚠️ Impossibile eseguire l'ordine: Capitale Operativo Disponibile pari a 0.00 EUR.")
            else:
                print(f"🛑 AI Guard: OPERAZIONE BLOCCATA -> {reason}")
        else:
            print(f"⚪ Nessun segnale operativo di ingresso per {symbol} (Prezzo: {analysis['price']:.2f} EUR)")

if __name__ == "__main__":
    run()
