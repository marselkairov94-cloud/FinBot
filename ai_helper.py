import os
import json
import re
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Модели для двух отдельных задач
PARSER_MODEL = os.getenv("OPENROUTER_PARSER_MODEL", "google/gemini-2.0-flash-lite-preview:free")
PET_MODEL = os.getenv("OPENROUTER_PET_MODEL", "openrouter/free")

client: Optional[OpenAI] = None
if OPENROUTER_API_KEY:
    try:
        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            timeout=10.0
        )
    except Exception as e:
        print(f"[AI] Ошибка инициализации клиента OpenAI: {e}")

VALID_CATEGORIES = [
    "Еда и фастфуд",
    "Транспорт",
    "Маркетплейсы",
    "Игры и подписки",
    "Другое"
]

CATEGORY_KEYWORDS = {
    "Еда и фастфуд": [
        "вод", "кофе", "чай", "обед", "ужин", "завтрак", "ед", "фастфуд",
        "пицц", "бургер", "шаурм", "донер", "столов", "кафе", "продукт",
        "ресторан", "напит", "снек", "чипс", "шоколад", "морожен", "булочк",
        "хлеб", "сок", "латте", "капучино", "додо", "kfc", "кфс", "мак",
        "перекус", "суши", "ролл", "макдональдс", "бургер кинг"
    ],
    "Транспорт": [
        "автобус", "такси", "яндекс", "uber", "убер", "метро", "проезд",
        "бензин", "самокат", "маршрутк", "поезд", "билет", "проездн",
        "заправк", "каршеринг", "парковк"
    ],
    "Маркетплейсы": [
        "wildberries", "вайлдберриз", "вб", "wb", "kaspi", "каспи", "ozon",
        "озон", "одежд", "обув", "кроссовк", "футболк", "штан", "куртк",
        "посылк", "маркетплейс"
    ],
    "Игры и подписки": [
        "steam", "стим", "игр", "playstation", "ps", "xbox", "донат",
        "подписк", "кино", "фильм", "музык", "spotify", "спотифай",
        "netflix", "нетфликс", "кинопоиск", "дискорд", "discord"
    ],
    "Другое": [
        "аптек", "лекарств", "таблетк", "подар", "канцтовар", "ручк",
        "тетрад", "стрижк", "парикмахер", "книг", "цвет"
    ]
}


def match_category_keywords(text: str) -> Optional[str]:
    """Быстрое сопоставление категории по ключевым словам и корням."""
    text_lower = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw), text_lower) or kw in text_lower:
                return cat
    return None


def parse_expense_with_ai(user_text: str) -> Optional[Dict[str, Any]]:
    """
    Модель 1: Быстрый парсер суммы и категории из естественного текста пользователя.
    Извлекает сумму траты (число) и категорию из строгого списка.
    Возвращает dict: {"amount": float, "category": str | None} или None.
    """
    matched_category = match_category_keywords(user_text)

    if not client:
        return None

    system_prompt = (
        "Ты — точный финансовый парсер сообщений. "
        "Твоя задача — извлечь сумму расхода (число) и определить категорию из текста пользователя.\n\n"
        "Категория должна быть СТРОГО одной из следующих пяти:\n"
        "1. 'Еда и фастфуд' (еда, вода, обед, кофе, чай, шаурма, пицца, бургер, перекус, продукты, столовая, кафе, ресторан, напитки)\n"
        "2. 'Транспорт' (автобус, такси, метро, проезд, бензин, самокат, маршрутка, поезд, билет на транспорт)\n"
        "3. 'Маркетплейсы' (Wildberries, Kaspi, Ozon, одежда, обувь, вещи, онлайн-заказ, покупка товара)\n"
        "4. 'Игры и подписки' (игры, Steam, PlayStation, Xbox, донат, кино, музыка, Netflix, Spotify, подписки)\n"
        "5. 'Другое' (аптека, лекарства, канцтовары, подарки, книги, стрижка, прочие расходы)\n\n"
        "Правила:\n"
        "- Если категория прямо не указана и не ясна из контекста, верни null в поле category.\n"
        "- Извлеки только сумму (числом) в поле amount.\n"
        "- Верни ответ СТРОГО в формате JSON без markdown и без пояснений:\n"
        '{"amount": число, "category": "название категории или null"}'
    )

    try:
        response = client.chat.completions.create(
            model=PARSER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0.1
        )
        
        result_text = response.choices[0].message.content
        if not result_text:
            return None

        clean_json = result_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        json_match = re.search(r'\{.*\}', clean_json, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)

        expense_data = json.loads(clean_json)

        if "amount" in expense_data and expense_data["amount"] is not None:
            try:
                amt = float(expense_data["amount"])
                if amt > 0:
                    cat = expense_data.get("category")
                    if cat and isinstance(cat, str) and cat.lower() != "null":
                        for vc in VALID_CATEGORIES:
                            if vc.lower() == cat.lower() or vc.lower() in cat.lower() or cat.lower() in vc.lower():
                                matched_category = vc
                                break
                    
                    return {
                        "amount": amt,
                        "category": matched_category
                    }
            except (ValueError, TypeError):
                pass
        return None

    except Exception as e:
        print(f"[AI Parser] Ошибка при парсинге расхода: {e}")
        return None


def generate_pet_response(
    category: str,
    amount: float,
    is_spontaneous: bool,
    current_hp: int,
    pet_level: int = 1,
    pet_name: str = "Тамагочи"
) -> str:
    """
    Модель 2: Ролевая модель Тамагочи.
    Генерирует короткую (1-2 предложения) реакцию питомца на трату.
    """
    if client:
        system_prompt = (
            f"Ты — виртуальный финансовый питомец Тамагочи по имени {pet_name} "
            f"(уровень: {pet_level}, здоровье: {current_hp}/100). "
            "Твоя задача — дать короткую реакцию на покупку хозяина. "
            "Если трата спонтанная или произошел перерасход лимита, ты огорчен и потерял здоровье. "
            "Если трата запланированная, ты радуешься, чувствуешь прилив сил и хвалишь за дисциплину. "
            "Требования: строго 1-2 коротких предложения, живой и дружелюбный тон, "
            "без эмоджи, без звездочек, без многоточий и без сложного форматирования."
        )

        user_prompt = (
            f"Хозяин совершил покупку на {amount:,.0f} ₸ в категории '{category}'. "
            f"Тип покупки: {'Спонтанно' if is_spontaneous else 'Запланировано'}. "
            f"Твое текущее здоровье: {current_hp}/100."
        )

        try:
            response = client.chat.completions.create(
                model=PET_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            if content:
                clean_text = content.strip().replace("**", "").replace("*", "").replace("...", ".")
                if clean_text:
                    return clean_text
        except Exception as e:
            print(f"[AI Pet] Ошибка генерации реплики питомца: {e}")

    # Фоллбек-ответы
    if is_spontaneous:
        if current_hp <= 25:
            return "Ой, из-за этой спонтанной покупки мне совсем нехорошо. Пожалуйста, будь внимательнее к бюджету."
        return "Ой, эта незапланированная покупка отняла у меня немного сил. Давай в следующий раз спланируем трату заранее."
    else:
        return "Отличная запланированная покупка. Я получил опыт и чувствую себя замечательно благодаря твоей дисциплине."