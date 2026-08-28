import json
import re

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

    # ========================================================
    # ESTRAZIONE JSON
    # ========================================================

    @staticmethod
    def _extract_json(text):

        text = text.strip()

        # Rimuove eventuali ```json ... ```
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"\s*```$",
            "",
            text
        )

        return json.loads(text)

    # ========================================================
    # AI RISK GUARD
    # ========================================================

    def evaluate_market_risk(
        self,
        asset,
        side,
        current_price,
        technical_data=None
    ):

        technical_data = technical_data or {}

        prompt = f"""
Sei il modulo di controllo rischio di un trading bot
automatico.

NON devi generare segnali di trading.

La strategia quantitativa ha già generato questo segnale:

ASSET: {asset}
DIREZIONE: {side}
PREZZO: {current_price} EUR

DATI TECNICI:
{json.dumps(technical_data, indent=2)}

Il tuo unico compito è verificare se esistono elementi
evidenti nei dati forniti che rendono il segnale
particolarmente rischioso o incoerente.

Non inventare news, prezzi, indicatori o eventi che non
sono presenti nei dati forniti.

Rispondi ESCLUSIVAMENTE con JSON valido:

{{
    "decision": "BLOCK" oppure "GO",
    "reason": "breve motivazione"
}}

Regole:

BLOCK:
- dati incoerenti;
- rischio anomalo evidente;
- informazioni insufficienti per effettuare il controllo.

GO:
- non rilevi anomalie evidenti nei dati forniti.

Non modificare entry, stop loss, take profit o size.
"""

        try:

            response = self.client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=200,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            if not response.content:
                raise RuntimeError(
                    "Risposta Anthropic vuota"
                )

            text = response.content[0].text

            result = self._extract_json(text)

            decision = (
                str(
                    result.get(
                        "decision",
                        "BLOCK"
                    )
                )
                .upper()
                .strip()
            )

            reason = str(
                result.get(
                    "reason",
                    "Nessuna motivazione"
                )
            )

            if decision not in (
                "GO",
                "BLOCK"
            ):
                decision = "BLOCK"
                reason = (
                    "Decisione Anthropic non valida"
                )

            return {
                "decision": decision,
                "reason": reason
            }

        except Exception as e:

            print(
                f"ERRORE ANTHROPIC: {e}"
            )

            # FAIL CLOSED:
            # se Anthropic non funziona,
            # non apriamo nessun trade.
            return {
                "decision": "BLOCK",
                "reason": (
                    "Anthropic non disponibile. "
                    "Trade bloccato per sicurezza."
                )
            }
