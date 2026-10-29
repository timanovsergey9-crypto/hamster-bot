import os
import requests
import random

TOKEN = os.getenv("BOT_TOKEN")
CHAT_FINANCE = os.getenv("CHAT_FINANCE")
CHAT_QUOTES = os.getenv("CHAT_QUOTES")

def send(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

def morning_finance():
    fng = requests.get("https://api.alternative.me/fng/?limit=1").json()["data"][0]
    global_data = requests.get("https://api.coingecko.com/api/v3/global").json()["data"]
    prices = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true").json()

    text = f"""📊 <b>Утренний обзор | Палата Хомяка</b>

😨 Индекс страха и жадности: {fng['value']} ({fng['value_classification']})

📈 Рынок сейчас:
• BTC: ${prices['bitcoin']['usd']:,.0f} ({prices['bitcoin']['usd_24h_change']:+.1f}%)
• ETH: ${prices['ethereum']['usd']:,.0f} ({prices['ethereum']['usd_24h_change']:+.1f}%)
• Доминация BTC: {global_data['market_cap_percentage']['btc']:.1f}%

⚠️ Информационный контент. Не является финансовой рекомендацией."""
    send(CHAT_FINANCE, text)

def evening_finance():
    prices = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true").json()
    text = f"""🌙 <b>Вечерний итог | Палата Хомяка</b>

За сегодня:
• BTC: ${prices['bitcoin']['usd']:,.0f} ({prices['bitcoin']['usd_24h_change']:+.1f}%)
• ETH: ${prices['ethereum']['usd']:,.0f} ({prices['ethereum']['usd_24h_change']:+.1f}%)

⚠️ Информационный контент. Не является финансовой рекомендацией."""
    send(CHAT_FINANCE, text)

def morning_quotes():
    try:
        q = requests.get("http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=ru", timeout=10).json()
        quote = q.get("quoteText", "").strip()
        author = q.get("quoteAuthor", "").strip() or "Неизвестный автор"
    except:
        quote = "Дисциплина — это мост между целями и достижениями."
        author = "Наполеон Хилл"
    text = f"""🌅 <b>Доброе утро, Хомяк Live</b>

«{quote}»
— {author}

Сегодня действуй. Не откладывай."""
    send(CHAT_QUOTES, text)

def evening_quotes():
    try:
        q = requests.get("http://api.forismatic.com/api/1.0/?method=getQuote&format=json&lang=ru", timeout=10).json()
        quote = q.get("quoteText", "").strip()
        author = q.get("quoteAuthor", "").strip() or "Неизвестный автор"
    except:
        quote = "Сила воли — это мышца. Тренируй её каждый день."
        author = ""
    text = f"""🌙 <b>Спокойной ночи, Хомяк Live</b>

«{quote}»
— {author}

Отдыхай. Завтра снова в бой."""
    send(CHAT_QUOTES, text)

if __name__ == "__main__":
    mode = os.getenv("MODE", "morning_finance")
    if mode == "morning_finance":
        morning_finance()
    elif mode == "evening_finance":
        evening_finance()
    elif mode == "morning_quotes":
        morning_quotes()
    elif mode == "evening_quotes":
        evening_quotes()
