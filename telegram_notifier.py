import os
import urllib.parse
import urllib.request


TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    ""
).strip()

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    ""
).strip()


def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configurato.")
        return False

    try:
        url = (
            f"https://api.telegram.org/bot"
            f"{TELEGRAM_BOT_TOKEN}/sendMessage"
        )

        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            method="POST"
        )

        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:

            if response.status == 200:
                print("Messaggio Telegram inviato.")
                return True

            print(
                f"Errore Telegram HTTP: "
                f"{response.status}"
            )
            return False

    except Exception as e:
        print(f"Errore invio Telegram: {e}")
        return False


def notify_trade_open(
    symbol,
    side,
    entry,
    stop_loss,
    take_profit,
    notional,
    risk
):
    message = (
        "🚀 <b>NUOVA OPERAZIONE</b>\n\n"
        f"Asset: <b>{symbol}</b>\n"
        f"Direzione: <b>{side}</b>\n"
        f"Entry: {entry:.2f}\n"
        f"Stop Loss: {stop_loss:.2f}\n"
        f"Take Profit: {take_profit:.2f}\n"
        f"Controvalore: {notional:.2f} EUR\n"
        f"Rischio stimato: {risk:.2f} EUR"
    )

    return send_telegram_message(message)


def notify_take_profit(
    symbol,
    side,
    entry,
    exit_price,
    profit
):
    message = (
        "✅ <b>TAKE PROFIT</b>\n\n"
        f"Asset: <b>{symbol}</b>\n"
        f"Operazione: {side}\n"
        f"Entry: {entry:.2f}\n"
        f"Uscita: {exit_price:.2f}\n"
        f"Profitto: <b>+{profit:.2f} EUR</b>"
    )

    return send_telegram_message(message)


def notify_stop_loss(
    symbol,
    side,
    entry,
    exit_price,
    loss
):
    message = (
        "🛑 <b>STOP LOSS</b>\n\n"
        f"Asset: <b>{symbol}</b>\n"
        f"Operazione: {side}\n"
        f"Entry: {entry:.2f}\n"
        f"Uscita: {exit_price:.2f}\n"
        f"Perdita: <b>-{abs(loss):.2f} EUR</b>"
    )

    return send_telegram_message(message)


def notify_daily_report(
    balance,
    operating_capital,
    btc_status,
    eth_status
):
    message = (
        "📊 <b>REPORT GIORNALIERO CRYPTO BOT</b>\n\n"
        f"Saldo Kraken: {balance:.2f} EUR\n"
        f"Capitale operativo: "
        f"{operating_capital:.2f} EUR\n\n"
        f"BTC: {btc_status}\n"
        f"ETH: {eth_status}\n\n"
        "Bot operativo ✅"
    )

    return send_telegram_message(message)
