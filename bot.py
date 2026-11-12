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
CHAT_HYPE = os.getenv("CHAT_HYPE") or "@ELEVATIONLIVE"
XAI_API_KEY = os.getenv("XAI_API_KEY")
TIMEOUT = 30
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
        logger.error(f"Не заданы TOKEN или CHAT_ID (chat_id={chat_id})")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        logger.info(f"Сообщение отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки в {chat_id}: {e}")
        return False

def send_photo(chat_id: str, photo_url: str, caption: str) -> bool:
    if not TOKEN or not chat_id:
        logger.error("Не заданы TOKEN или CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        logger.info(f"Фото отправлено в {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        return False

# ==================== GROK ====================

def call_grok(system: str, user_prompt: str, use_tools: bool = False) -> Optional[str]:
    if not XAI_API_KEY:
        logger.error("XAI_API_KEY не задан")
        return None

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "grok-3",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.9,
        "max_tokens": 1000
    }

    if use_tools:
        payload["tools"] = [
            {"type": "web_search"},
            {"type": "x_search"}
        ]

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            logger.error(f"Grok API error {resp.status_code}: {resp.text[:500]}")
            if use_tools:
                logger.info("Пробуем без tools...")
                return call_grok(system, user_prompt, use_tools=False)
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        logger.info("Grok успешно сгенерировал пост")
        return content
    except Exception as e:
        logger.error(f"Ошибка вызова Grok: {e}")
        return None

def topic_for_slot(items, slot: str):
    """Детерминированная ротация: разные темы в течение дня, без случайного выбора."""
    offsets = {"morning": 0, "midday": 4, "evening": 8}
    day_index = datetime.now(MSK).timetuple().tm_yday - 1
    return items[(day_index + offsets.get(slot, 0)) % len(items)]


def grok_finance_post(slot: str):
    system = """Ты редактор Telegram-канала «Палата Хомяка» — медиа о крипторынке для обычных людей.
Пиши конкретно, понятно и с характером. Никаких сигналов «покупай/продавай», обещаний доходности и выдуманных фактов.
Формат: цепляющий заголовок → конкретный пример или объяснение → практический вывод.
Длина 650–1100 символов. Не заканчивай дежурным вопросом к читателю.
Если приводишь цифры, события или новости — используй только проверяемые данные из доступных источников; если данных нет, не выдумывай.
В конце добавляй: ⚠️ Информационный материал, не финансовая рекомендация."""

    topics = [
        ("РАЗБОР ОШИБКИ", "Почему усреднение убытка без заранее заданного плана превращается в ловушку. Покажи условный пример без выдуманных рыночных цифр."),
        ("СЛОВАРЬ ХОМЯКА", "Объясни ликвидацию простыми словами на бытовой аналогии и покажи, чем она отличается от обычного убытка."),
        ("МИФ ИЛИ ФАКТ", "Разбери миф, что низкая цена одной монеты означает, что она недооценена. Объясни роль капитализации и предложения."),
        ("КЕЙС", "Разбери типичный сценарий FOMO: человек видит резкий рост, входит поздно и не понимает план выхода. Дай три урока."),
        ("ИНСТРУМЕНТ", "Объясни, что такое стоп-лосс, какие задачи он решает и почему он не гарантирует точную цену исполнения."),
        ("РАЗБОР МАНИПУЛЯЦИИ", "Объясни признаки pump-and-dump и как не путать громкие обещания с доказательствами."),
        ("ПСИХОЛОГИЯ РЫНКА", "Почему после серии удачных сделок трейдер начинает нарушать собственные правила. Дай практический способ остановиться."),
        ("СЛОВАРЬ ХОМЯКА", "Объясни funding rate: кто кому платит, зачем существует механизм и почему его нельзя трактовать как готовый сигнал."),
        ("ЧЕК-ЛИСТ", "Дай короткий чек-лист из пяти пунктов, который стоит пройти перед любой сделкой, не предлагая конкретную сделку."),
        ("МИФ ИЛИ ФАКТ", "Разбери утверждение «крупный кошелёк покупает — значит цена вырастет». Объясни ограничения ончейн-наблюдений."),
        ("КЕЙС", "Покажи на условном примере, как плечо увеличивает не только потенциальный результат, но и скорость потери залога."),
        ("РАЗБОР НОВОСТИ", "Объясни, как отличать важную новость для крипторынка от шума. Не придумывай конкретную новость; дай критерии проверки.")
    ]
    label, topic = topic_for_slot(topics, slot)
    prompts = {
        "morning": f"Рубрика «{label}». Подготовь утренний полезный материал на тему: {topic}",
        "midday": f"Рубрика «{label}». Сделай самостоятельный разбор с примером и практическим выводом: {topic}",
        "evening": f"Рубрика «{label}». Подведи спокойный итог дня через понятный кейс или инструкцию: {topic}"
    }
    text = call_grok(system, prompts.get(slot, prompts["midday"]), use_tools=True)
    if text:
        if "не является финансовой рекомендацией" not in text.lower():
            text += "\n\n⚠️ <i>Информационный материал, не финансовая рекомендация.</i>"
        send(CHAT_FINANCE, text)
    else:
        logger.error(f"Не удалось сгенерировать Grok-пост ({slot})")


def grok_motivation_post():
    """Авторская ежедневная публикация для ELEVATIONLIVE."""
    target = CHAT_HYPE or "@ELEVATIONLIVE"
    logger.info(f"Отправляем материал в: {target}")

    system = """Ты автор ELEVATIONLIVE — канала о внутренней опоре, дисциплине и личном росте.
Не пиши дешёвую мотивацию, лозунги, банальные цитаты и пересказ чужих книг.
Пиши как умный собеседник: честно, конкретно, спокойно, иногда жёстко.
Каждый пост должен содержать узнаваемую жизненную ситуацию, одну сильную мысль и применимый вывод.
Не выдумывай личные истории от первого лица и не приписывай авторам несуществующие цитаты.
Длина 600–1000 символов. Заверши фразой, которую хочется сохранить или переслать."""

    themes = [
        ("НЕОЧЕВИДНАЯ ПРАВДА", "Почему постоянная занятость иногда помогает избегать действительно важного решения."),
        ("МИКРОПРАКТИКА", "Упражнение на 10 минут, чтобы перестать откладывать неприятную, но важную задачу."),
        ("ЖИЗНЕННЫЙ СЦЕНАРИЙ", "Человек сравнивает свой первый год пути с чужим десятым. Объясни, почему это ломает мотивацию."),
        ("ДИСЦИПЛИНА", "Что делать в день, когда нет ни сил, ни вдохновения: минимальный план вместо героизма."),
        ("РАЗБОР ПРИВЫЧКИ", "Почему обещание «с понедельника начну» часто не работает и как уменьшить первый шаг."),
        ("ПСИХОЛОГИЯ", "Как отличить здоровый отдых от избегания и не обвинять себя без причины."),
        ("КОРОТКАЯ ИСТОРИЯ", "Построй небольшую вымышленную, но реалистичную историю о цене маленьких ежедневных решений."),
        ("МЫСЛЬ ДЛЯ СОХРАНЕНИЯ", "Почему умение выдерживать неопределённость важнее постоянной уверенности."),
        ("ПРАКТИЧЕСКИЙ ШАГ", "Три вопроса, которые помогают понять, куда уходит время и что пора убрать."),
        ("АНТИМИФ", "Развенчай идею, что сильные люди никогда не сомневаются. Покажи разницу между сомнением и отказом действовать."),
        ("ЛИЧНЫЕ ГРАНИЦЫ", "Почему не каждое чужое ожидание должно становиться твоей обязанностью."),
        ("ВОССТАНОВЛЕНИЕ", "Как вернуться к делу после срыва режима без самобичевания и обещаний начать новую жизнь.")
    ]
    label, theme = topic_for_slot(themes, "morning")
    user_prompt = f"""Формат рубрики «{label}».
Напиши самостоятельную публикацию на тему: {theme}
Начни с сильного наблюдения, затем раскрой мысль через конкретную ситуацию и закончи практичным выводом.
Не задавай читателю вопрос ради комментариев. Текст должен быть ценным сам по себе."""

    text = call_grok(system, user_prompt, use_tools=False)
    if text:
        send(target, text)
    else:
        logger.error("Не удалось сгенерировать публикацию ELEVATIONLIVE")


# ==================== СТАРАЯ ЛОГИКА ====================

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

if __name__ == "__main__":
    mode = os.getenv("MODE", "morning_finance")
    logger.info(f"Запуск в режиме: {mode}")
    modes = {
        "morning_finance": morning_finance,
        "midday_finance": midday_finance,
        "afternoon_finance": afternoon_finance,
        "evening_finance": evening_finance,
        "grok_morning": lambda: grok_finance_post("morning"),
        "grok_midday": lambda: grok_finance_post("midday"),
        "grok_evening": lambda: grok_finance_post("evening"),
        "grok_motivation": grok_motivation_post,
    }
    func = modes.get(mode)
    if func:
        func()
    else:
        logger.error(f"Неизвестный режим: {mode}")
