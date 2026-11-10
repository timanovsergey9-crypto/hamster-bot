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

def grok_finance_post(slot: str):
    system = """Ты автор Telegram-канала «Палата Хомяка».
Пишешь живые, полезные, честные посты про крипту, рынок, психологию трейдинга, сленг и типичные ошибки.
Стиль: прямой, с характером, без воды и пафоса. Можно с лёгкой иронией.
Длина: 500–900 символов.
Структура: заголовок с эмодзи → основной текст → короткий вывод или вопрос.
Не давай финансовых рекомендаций. Всегда добавляй в конце дисклеймер.
Каждый пост должен быть максимально уникальным и свежим."""

    topics = [
        "психология FOMO и как с ней бороться",
        "разбор сленга: что такое 'to the moon', 'rug pull', 'diamond hands'",
        "популярная ошибка: усреднение убыточных позиций без плана",
        "психология жадности и страха на рынке",
        "разбор сленга: 'HODL', 'dump', 'pump and dump'",
        "частая ошибка новичков: торговля на эмоциях",
        "психология принятия убытков",
        "что такое 'leverage' и почему большинство его неправильно использует",
        "ошибка: отсутствие риск-менеджмента",
        "психология: почему люди покупают на хаях",
        "разбор: 'paper hands' vs 'diamond hands'",
        "типичная ошибка: игнорирование новостей и фундаментала",
    ]
    topic = random.choice(topics)

    prompts = {
        "morning": f"Напиши утренний живой пост для Палаты Хомяка на тему: {topic}. Можно упомянуть текущий рынок, если уместно. Сделай полезно и по-человечески.",
        "midday": f"Напиши дневной пост для Палаты Хомяка. Разбери тему: {topic}. Сделай живо и полезно.",
        "evening": f"Напиши вечерний пост для Палаты Хомяка на тему: {topic}. Дай мысли на ночь или полезный вывод. Стиль живой и честный."
    }

    text = call_grok(system, prompts.get(slot, prompts["midday"]), use_tools=True)
    if text:
        if "не является" not in text.lower() and "рекомендац" not in text.lower():
            text += "\n\n⚠️ <i>Информационный контент. Не является финансовой рекомендацией.</i>"
        send(CHAT_FINANCE, text)
    else:
        logger.error(f"Не удалось сгенерировать Grok-пост ({slot})")

# The rest of the file remains the same as original for other functions
# (motivation, market data, etc. are unchanged for brevity in this update, but in practice full file is used)

if __name__ == "__main__":
    mode = os.getenv("MODE", "morning_finance")
    logger.info(f"Запуск в режиме: {mode}")
    # ... (full modes dict as in original)
    print("Updated Grok section for unique psychology/slang/mistake posts")
