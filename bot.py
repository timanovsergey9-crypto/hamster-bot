import os
import requests
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
CHAT_FINANCE = os.getenv("CHAT_FINANCE")
CHAT_QUOTES = os.getenv("CHAT_QUOTES")
TIMEOUT = 15
MSK = timezone(timedelta(hours=3))

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

def get_market_data():
    fng = safe_get("https://api.alternative.me/fng/?limit=1")
    fng_value = fng["data"][0] if fng and "data" in fng else {"value": "?", "value_classification": "N/A"}
    
    global_data = safe_get("https://api.coingecko.com/api/v3/global")
    global_info = global_data.get("data", {}) if global_data else {}
    
    prices = safe_get("https://api.coingecko.com/api/v3/simple/price", params={
        "ids": "bitcoin,ethereum,solana,binancecoin",
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    })
    
    markets = safe_get("https://api.coingecko.com/api/v3/coins/markets", params={
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 30,
        "page": 1,
        "price_change_percentage": "24h"
    })
    
    trending = safe_get("https://api.coingecko.com/api/v3/search/trending")
    
    return {
        "fng": fng_value,
        "global": global_info,
        "prices": prices or {},
        "markets": markets or [],
        "trending": trending or {}
    }

def get_economic_calendar(days_ahead: int = 1) -> List[Dict]:
    data = safe_get("https://pipatlas.com/api/calendar")
    if not data or "events" not in data:
        return []
    
    now = datetime.now(MSK)
    today = now.date()
    result = []
    
    for ev in data["events"]:
        if ev.get("impact") not in ("High", "Medium"):
            continue
        try:
            # date примерно в формате ISO с оффсетом
            dt = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
            dt_msk = dt.astimezone(MSK)
            if dt_msk.date() == today or (dt_msk.date() - today).days <= days_ahead:
                result.append({
                    "name": ev.get("name", ""),
                    "currency": ev.get("currency", ""),
                    "impact": ev.get("impact", ""),
                    "time_msk": dt_msk.strftime("%H:%M"),
                    "forecast": ev.get("forecast", ""),
                    "previous": ev.get("previous", ""),
                    "dt": dt_msk
                })
        except Exception:
            continue
    
    # Сортируем по времени
    result.sort(key=lambda x: x["dt"])
    return result[:8]

def format_price(price_data, coin, symbol):
    if not price_data or coin not in price_data:
        return f"• {symbol}: нет данных"
    p = price_data[coin]
    change = p.get("usd_24h_change", 0)
    emoji = "🟢" if change >= 0 else "🔴"
    return f"• <b>{symbol}</b>: ${p['usd']:,.0f} ({emoji} {change:+.1f}%)"

def get_top_movers(markets, n=2):
    if not markets:
        return ""
    gainers = sorted(markets, key=lambda x: x.get("price_change_percentage_24h") or 0, reverse=True)[:n]
    losers = sorted(markets, key=lambda x: x.get("price_change_percentage_24h") or 0)[:n]
    
    g = "\n".join([f"🟢 {c['symbol'].upper()}: {c.get('price_change_percentage_24h', 0):+.1f}%" for c in gainers])
    l = "\n".join([f"🔴 {c['symbol'].upper()}: {c.get('price_change_percentage_24h', 0):+.1f}%" for c in losers])
    return f"<b>Топ движения:</b>\n{g}\n{l}"

def get_fng_comment(fng_value):
    try:
        val = int(fng_value)
        if val <= 25:
            return "Рынок в страхе. Такие уровни исторически часто были интересными для накопления, но никто не гарантирует дно."
        elif val <= 45:
            return "Осторожность. Многие ждут дальнейшего снижения."
        elif val <= 55:
            return "Нейтральная зона. Рынок в ожидании триггера."
        elif val <= 75:
            return "Жадность растёт. Многие уже в позициях."
        else:
            return "Экстремальная жадность. Исторически такие уровни часто предшествовали коррекциям."
    except:
        return ""

def event_comment(name: str) -> str:
    name_l = name.lower()
    if any(x in name_l for x in ["unemployment", "non-farm", "nfp", "employment"]):
        return " — сильно влияет на доллар и риск-активы. Лучше не торговать за 15–30 мин до и после."
    if any(x in name_l for x in ["cpi", "inflation", "pce"]):
        return " — ключевой показатель для ФРС и рынка. Высокая волатильность."
    if any(x in name_l for x in ["fomc", "rate", "interest", "monetary policy"]):
        return " — решение по ставке двигает все рынки. Особенно опасно."
    if "gdp" in name_l:
        return " — общий рост экономики, влияет на настроения."
    return ""

def morning_finance():
    data = get_market_data()
    if not data or not data.get("prices"):
        send(CHAT_FINANCE, "⚠️ Не удалось получить данные с рынка.")
        return
    
    fng = data["fng"]
    global_info = data["global"]
    prices = data["prices"]
    btc_dom = global_info.get("market_cap_percentage", {}).get("btc", 0)
    total_mcap = global_info.get("total_market_cap", {}).get("usd", 0)
    
    comment = get_fng_comment(fng.get("value", "50"))
    movers = get_top_movers(data.get("markets", []), 2)
    
    # Экономический календарь на сегодня
    calendar = get_economic_calendar(0)
    cal_text = ""
    if calendar:
        lines = []
        for ev in calendar:
            impact_emoji = "🔴" if ev["impact"] == "High" else "🟡"
            extra = event_comment(ev["name"])
            forecast = f" (прогноз: {ev['forecast']})" if ev["forecast"] else ""
            lines.append(f"{impact_emoji} {ev['time_msk']} МСК — {ev['currency']} {ev['name']}{forecast}{extra}")
        cal_text = "\n\n📅 <b>Важные новости сегодня:</b>\n" + "\n".join(lines) + "\n\n<i>Во время высокоимпактных новостей лучше не открывать новые позиции.</i>"
    
    text = f"""📊 <b>Утренний обзор | Палата Хомяка</b>

😨 Индекс страха и жадности: <b>{fng['value']}</b> ({fng['value_classification']})
<i>{comment}</i>

📈 <b>Рынок сейчас:</b>
{format_price(prices, 'bitcoin', 'BTC')}
{format_price(prices, 'ethereum', 'ETH')}
{format_price(prices, 'solana', 'SOL')}
{format_price(prices, 'binancecoin', 'BNB')}

👑 Доминация BTC: {btc_dom:.1f}%
💰 Общая капитализация: ${total_mcap/1e12:.2f}T

{movers}{cal_text}

⚠️ <i>Информационный контент. Не является финансовой рекомендацией.</i>"""
    send(CHAT_FINANCE, text)

def midday_finance():
    data = get_market_data()
    if not data:
        send(CHAT_FINANCE, "⚠️ Данные временно недоступны.")
        return
    
    trending = data.get("trending", {}).get("coins", [])[:3]
    trending_text = "\n".join([f"• {c['item']['name']} ({c['item']['symbol']})" for c in trending]) if trending else "Нет данных"
    movers = get_top_movers(data.get("markets", []), 3)
    
    text = f"""💡 <b>Дневной срез | Палата Хомяка</b>

🔥 <b>Сейчас в тренде:</b>
{trending_text}

{movers}

Рынок живёт своей жизнью. Кто-то уже заработал, кто-то ждёт. А ты где сегодня?

⚠️ <i>Информационный контент.</i>"""
    send(CHAT_FINANCE, text)

def afternoon_finance():
    data = get_market_data()
    prices = data.get("prices", {}) if data else {}
    
    text = f"""📉 <b>К вечеру | Палата Хомяка</b>

Краткий срез:
{format_price(prices, 'bitcoin', 'BTC')}
{format_price(prices, 'ethereum', 'ETH')}

Если утром был страх — проверь, не изменилось ли что-то к вечеру.
Если была жадность — не забывай фиксировать часть прибыли.

Как твой день прошёл?

⚠️ <i>Информационный контент.</i>"""
    send(CHAT_FINANCE, text)

def evening_finance():
    data = get_market_data()
    if not data or not data.get("prices"):
        send(CHAT_FINANCE, "⚠️ Не удалось получить вечерние данные.")
        return
    
    prices = data["prices"]
    fng = data["fng"]
    
    text = f"""🌙 <b>Вечерний итог | Палата Хомяка</b>

За сегодня:
{format_price(prices, 'bitcoin', 'BTC')}
{format_price(prices, 'ethereum', 'ETH')}
{format_price(prices, 'solana', 'SOL')}

😨 Fear & Greed: {fng.get('value', '?')}

Завтра новый день. Отдыхай и не перетрейвай графики ночью.

⚠️ <i>Информационный контент. Не является финансовой рекомендацией.</i>"""
    send(CHAT_FINANCE, text)

def get_quote():
    q = safe_get("http://api.forismatic.com/api/1.0/", params={"method": "getQuote", "format": "json", "lang": "ru"})
    if q and "quoteText" in q:
        return q["quoteText"].strip(), q.get("quoteAuthor", "").strip() or "Неизвестный автор"
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
    comments = [
        "Сегодня сделай одно маленькое действие в сторону своей цели.",
        "Не жди мотивации. Начни — и она придёт.",
        "Один хороший шаг сегодня лучше десяти завтра.",
    ]
    text = f"""🌅 <b>Доброе утро, Хомяк Live</b>

«{quote}»
{author_line}

{random.choice(comments)}"""
    send(CHAT_QUOTES, text)

def evening_quotes():
    quote, author = get_quote()
    author_line = f"— {author}" if author else ""
    comments = [
        "Отдохни. Завтра снова в бой.",
        "Что ты сегодня сделал для своего будущего? Даже маленькое считается.",
        "Спокойной ночи. Завтра новые возможности.",
    ]
    text = f"""🌙 <b>Спокойной ночи, Хомяк Live</b>

«{quote}»
{author_line}

{random.choice(comments)}"""
    send(CHAT_QUOTES, text)

if __name__ == "__main__":
    mode = os.getenv("MODE", "morning_finance")
    logger.info(f"Запуск в режиме: {mode}")
    modes = {
        "morning_finance": morning_finance,
        "midday_finance": midday_finance,
        "afternoon_finance": afternoon_finance,
        "evening_finance": evening_finance,
        "morning_quotes": morning_quotes,
        "evening_quotes": evening_quotes,
    }
    func = modes.get(mode)
    if func:
        func()
    else:
        logger.error(f"Неизвестный режим: {mode}")
