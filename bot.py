import os
import requests
import logging
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
CHAT_FINANCE = os.getenv("CHAT_FINANCE")
CHAT_QUOTES = os.getenv("CHAT_QUOTES")
TIMEOUT = 15

def safe_get(url: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Ошибка запроса к {url}: {e}")
        return None

def send(chat_id: str, text: str) -> bool:
    if not TOKEN or not chat_id:
        logger.error("Не заданы TOKEN или CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        logger.info(f"Сообщение отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return False

def get_crypto_data():
    fng = safe_get("https://api.alternative.me/fng/?limit=1")
    fng_value = fng["data"][0] if fng and "data" in fng else {"value": "?", "value_classification": "N/A"}
    global_data = safe_get("https://api.coingecko.com/api/v3/global")
    global_info = global_data.get("data", {}) if global_data else {}
    prices = safe_get("https://api.coingecko.com/api/v3/simple/price", params={"ids": "bitcoin,ethereum,solana", "vs_currencies": "usd", "include_24hr_change": "true"})
    return {"fng": fng_value, "global": global_info, "prices": prices or {}}

def format_price(price_data, coin, symbol):
    if not price_data or coin not in price_data:
        return f"• {symbol}: нет данных"
    p = price_data[coin]
    change = p.get("usd_24h_change", 0)
    emoji = "🟢" if change >= 0 else "🔴"
    return f"• <b>{symbol}</b>: ${p['usd']:,.0f} ({emoji} {change:+.1f}%)"

def morning_finance():
    data = get_crypto_data()
    if not data or not data.get("prices"):
        send(CHAT_FINANCE, "⚠️ Не удалось получить данные с рынка.")
        return
    fng = data["fng"]
    global_info = data["global"]
    prices = data["prices"]
    btc_dom = global_info.get("market_cap_percentage", {}).get("btc", 0)
    total_mcap = global_info.get("total_market_cap", {}).get("usd", 0)
    text = f"""📊 <b>Утренний обзор | Палата Хомяка</b>

😨 Индекс страха и жадности: <b>{fng['value']}</b> ({fng['value_classification']})

📈 <b>Рынок сейчас:</b>
{format_price(prices, 'bitcoin', 'BTC')}
{format_price(prices, 'ethereum', 'ETH')}
{format_price(prices, 'solana', 'SOL')}

👑 Доминация BTC: {btc_dom:.1f}%
💰 Общая капитализация: ${total_mcap/1e12:.2f}T

⚠️ <i>Информационный контент. Не является финансовой рекомендацией.</i>"""
    send(CHAT_FINANCE, text)

def evening_finance():
    data = get_crypto_data()
    if not data or not data.get("prices"):
        send(CHAT_FINANCE, "⚠️ Не удалось получить вечерние данные.")
        return
    prices = data["prices"]
    text = f"""🌙 <b>Вечерний итог | Палата Хомяка</b>

За сегодня:
{format_price(prices, 'bitcoin', 'BTC')}
{format_price(prices, 'ethereum', 'ETH')}
{format_price(prices, 'solana', 'SOL')}

⚠️ <i>Информационный контент. Не является финансовой рекомендацией.</i>"""
    send(CHAT_FINANCE, text)

def get_quote():
    q = safe_get("http://api.forismatic.com/api/1.0/", params={"method": "getQuote", "format": "json", "lang": "ru"})
    if q and "quoteText" in q:
        return q["quoteText"].strip(), q.get("quoteAuthor", "").strip() or "Неизвестный автор"
    import random
    fallbacks = [
        ("Дисциплина — это мост между целями и достижениями.", "Наполеон Хилл"),
        ("Сила воли — это мышца. Тренируй её каждый день.", ""),
        ("Сегодня — лучший день, чтобы начать.", ""),
        ("Маленькие шаги каждый день приводят к большим результатам.", ""),
    ]
    return random.choice(fallbacks)

def morning_quotes():
    quote, author = get_quote()
    author_line = f"— {author}" if author else ""
    text = f"""🌅 <b>Доброе утро, Хомяк Live</b>

«{quote}»
{author_line}

Сегодня действуй. Не откладывай."""
    send(CHAT_QUOTES, text)

def evening_quotes():
    quote, author = get_quote()
    author_line = f"— {author}" if author else ""
    text = f"""🌙 <b>Спокойной ночи, Хомяк Live</b>

«{quote}»
{author_line}

Отдыхай. Завтра снова в бой."""
    send(CHAT_QUOTES, text)

if __name__ == "__main__":
    mode = os.getenv("MODE", "morning_finance")
    logger.info(f"Запуск в режиме: {mode}")
    modes = {
        "morning_finance": morning_finance,
        "evening_finance": evening_finance,
        "morning_quotes": morning_quotes,
        "evening_quotes": evening_quotes,
    }
    func = modes.get(mode)
    if func:
        func()
    else:
        logger.error(f"Неизвестный режим: {mode}")
