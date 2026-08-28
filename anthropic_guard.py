import json
import anthropic
import config


class AnthropicGuard:

    def __init__(self):

        if not config.ANTHROPIC_API_KEY:

            raise RuntimeError(
                "ANTHROPIC_API_KEY mancante"
            )

        self.client = anthropic.Anthropic(
            api_key=config.ANTHROPIC_API_KEY
        )


    def evaluate_news_impact(
        self,
        asset,
        side,
        current_price
    ):

        prompt = f"""
Sei un Risk Analyst per un bot quantitativo.

Asset: {asset}
Segnale tecnico: {side}
Prezzo: {current_price} EUR

Valuta se il contesto di mercato/news presenta
un rischio evidente contrario al segnale.

Rispondi ESCLUSIVAMENTE JSON:

{{
    "decision": "BLOCK" | "GO" | "BOOST_GO",
    "news_summary": "massimo una frase",
    "reason": "massimo due frasi"
}}
"""

        try:

            response = self.client.messages.create(

                model=config.ANTHROPIC_MODEL,

                max_tokens=250,

                temperature=0,

                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            text = response.content[0].text.strip()

            data = json.loads(text)

            decision = data.get(
                "decision",
                "BLOCK"
            )

            if decision not in [
                "BLOCK",
                "GO",
                "BOOST_GO"
            ]:

                decision = "BLOCK"

            return (
                decision,
                data.get(
                    "news_summary",
                    ""
                ),
                data.get(
                    "reason",
                    ""
                )
            )

        except Exception as e:

            print(
                f"❌ Anthropic error: {e}"
            )

            # FAIL SAFE:
            # se AI non funziona NON TRADIAMO
            return (
                "BLOCK",
                "AI non disponibile",
                "Trade bloccato per sicurezza"
            )
