import json
import anthropic
import config

class AnthropicGuard:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def evaluate_news_impact(self, asset, side, current_price):
        """
        Valuta il sentiment e le notizie di mercato rispetto al segnale generato.
        Restituisce: (decision, news_summary, reason)
        - decision: 'BLOCK', 'GO', 'BOOST_GO'
        """
        prompt = f"""Sei un News & Sentiment Risk Analyst per un bot di quantitative trading su criptovalute.
Il tuo compito è analizzare il contesto attuale delle notizie/sentiment per l'asset {asset} rispetto al segnale di trading generato.

Dati Operazione Proposta:
- Asset: {asset}
- Segnale Tecnico: {side}
- Prezzo Attuale: {current_price} EUR

REGOLE RIGIDE DI DECISIONE:
1. "BLOCK": Se ci sono notizie chiaramente CONTRARIE al segnale (es. segnale BUY ma ci sono news catastrofiche, FUD, hack, regolamentazioni punitive, o segnale SELL con news estremamente positive).
2. "GO": Se le notizie sono NEUTRE, assenti o bilanciate, oppure il mercato sta seguendo la dinamica normale senza news rilevanti.
3. "BOOST_GO": Se ci sono notizie fortemente A FAVORE del segnale (es. segnale BUY supportato da approvazioni normative, adozione, catalizzatori macro rialzisti, o segnale SELL con notizie fortemente negative sull'asset).

Rispondi ESCLUSIVAMENTE in formato JSON con la seguente struttura:
{{
    "decision": "BLOCK" oppure "GO" oppure "BOOST_GO",
    "news_summary": "Sintesi di 1 frase sul quadro notizie rilevato",
    "reason": "Spiegazione della decisione in massimo 2 frasi"
}}"""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=250,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            data = json.loads(text)
            
            return (
                data.get("decision", "GO"),
                data.get("news_summary", "Nessuna notizia rilevante"),
                data.get("reason", "Nessuna motivazione fornita")
            )
        except Exception as e:
            print(f"⚠️ Errore API Notizie AI: {e}. Fallback su decisione neutra (GO).")
            return "GO", "Errore API", "Fallback di sicurezza su leva standard"
