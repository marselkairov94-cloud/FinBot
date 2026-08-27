import re
from datetime import datetime
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import default_state
from aiogram.types import Message, CallbackQuery

from ai_helper import parse_expense_with_ai, generate_pet_response, match_category_keywords
from database.storage import storage
from database.models import ExpenseRecord
from services.algorithm import calculate_expense_impact
from keyboards.inline import get_categories_keyboard, get_impulsiveness_keyboard
from config import CURRENCY_SYMBOL, EXPENSE_CATEGORIES

router = Router()

MENU_BUTTONS = {
    "Накопить на цель",
    "Контролировать лимит",
    "Питомец",
    "Мой питомец",
    "Тамагочи",
    "Текущий статус",
    "Мой статус",
    "Сбросить настройки",
    "Сброс",
    "Reset",
    "reset",
    "Статус"
}


def render_progress_bar(value: int, max_val: int = 100, length: int = 10) -> str:
    """Генерирует визуальную шкалу прогресса, например [████████░░]."""
    val = max(0, min(max_val, value))
    filled = int((val / max_val) * length) if max_val > 0 else 0
    filled = max(0, min(length, filled))
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}]"


def extract_first_number(text: str) -> Optional[float]:
    """
    Умный извлекатель суммы расхода из свободного текста.
    Распознает форматы: '10', '1200', '1 200', '25 000', '150.50', '150,50', '10тг', '10 тг'.
    """
    text_clean = text.replace("\xa0", " ").strip()
    
    # 1. Поиск чисел с пробелами тысяч (например: 25 000, 100 000)
    match_thousands = re.search(r'\b(\d{1,3}(?:[ ]\d{3})+)(?:[.,](\d{1,2}))?\b', text_clean)
    if match_thousands:
        int_part = match_thousands.group(1).replace(" ", "")
        frac_part = match_thousands.group(2)
        val_str = f"{int_part}.{frac_part}" if frac_part else int_part
        try:
            val = float(val_str)
            if val > 0:
                return val
        except ValueError:
            pass

    # 2. Поиск стандартного первого числа в тексте
    match = re.search(r'(\d+(?:[.,]\d+)?)', text_clean)
    if match:
        val_str = match.group(1).replace(",", ".")
        try:
            val = float(val_str)
            if val > 0:
                return val
        except ValueError:
            pass

    return None


@router.message(Command("pet"))
@router.message(F.text.in_(["Питомец", "Мой питомец", "Тамагочи"]))
async def show_pet_card(message: Message):
    """Карточка состояния виртуального питомца (Тамагочи)."""
    user_id = message.from_user.id
    user = storage.get_user(user_id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return

    hp_bar = render_progress_bar(user.pet_hp, 100, 10)
    exp_bar = render_progress_bar(user.pet_exp, 100, 10)

    lines = [
        f"Питомец: {user.pet_name}",
        "────────────────────",
        f"Уровень: {user.pet_level}",
        f"Здоровье (HP): {hp_bar} {user.pet_hp}/100",
        f"Опыт (EXP): {exp_bar} {user.pet_exp}/100",
        "────────────────────",
        "Правила заботы о питомце:",
        "• Запланированная покупка: +10 EXP (при 100 EXP повышается уровень и восстанавливается +20 HP).",
        "• Спонтанная покупка: -15 HP.",
        "• Перерасход дневного лимита: -10 HP.",
        "\nОтправьте сумму или текст расхода в чат, чтобы развивать питомца."
    ]
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def show_spending_stats(message: Message):
    """Команда для вывода статистики расходов и состояния питомца."""
    user_id = message.from_user.id
    user = storage.get_user(user_id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return

    expenses = storage.get_user_expenses(user.nickname)
    
    if not expenses:
        hp_bar = render_progress_bar(user.pet_hp, 100, 10)
        exp_bar = render_progress_bar(user.pet_exp, 100, 10)
        await message.answer(
            f"У вас пока нет записанных расходов.\n\n"
            f"Питомец {user.pet_name}:\n"
            f"Уровень: {user.pet_level}\n"
            f"Здоровье (HP): {hp_bar} {user.pet_hp}/100\n"
            f"Опыт (EXP): {exp_bar} {user.pet_exp}/100\n\n"
            f"Отправьте сумму или текст покупки в чат."
        )
        return

    category_totals = {}
    total_spent = 0.0
    total_spontaneous = 0.0

    for exp in expenses:
        category_totals[exp.category] = category_totals.get(exp.category, 0.0) + exp.amount
        total_spent += exp.amount
        if exp.expense_type == "Спонтанно":
            total_spontaneous += exp.amount

    report = [
        "Статистика расходов",
        "────────────────────",
        f"Пользователь: {user.nickname}",
        f"Всего потрачено: {total_spent:,.0f} {CURRENCY_SYMBOL}",
        f"Спонтанных покупок: {total_spontaneous:,.0f} {CURRENCY_SYMBOL}\n",
        "По категориям:"
    ]

    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    for cat, amt in sorted_cats:
        percent = (amt / total_spent) * 100 if total_spent > 0 else 0.0
        report.append(f"{cat}: {amt:,.0f} {CURRENCY_SYMBOL} ({percent:.1f}%)")

    hp_bar = render_progress_bar(user.pet_hp, 100, 10)
    exp_bar = render_progress_bar(user.pet_exp, 100, 10)
    report.append("\n────────────────────")
    report.append(f"Питомец {user.pet_name}:")
    report.append(f"Уровень: {user.pet_level}")
    report.append(f"Здоровье (HP): {hp_bar} {user.pet_hp}/100")
    report.append(f"Опыт (EXP): {exp_bar} {user.pet_exp}/100")

    await message.answer("\n".join(report))


@router.message(default_state, F.text & ~F.text.startswith('/'))
async def process_expense_amount_input(message: Message):
    """
    Обработка текстового ввода расходов (срабатывает ТОЛЬКО вне FSM-состояний).
    Сумма не прибавляется в базу здесь, а передается в callback_data!
    """
    # Игнорируем кнопки меню
    if message.text.strip() in MENU_BUTTONS:
        return

    user = storage.get_user(message.from_user.id)
    if not user or not user.nickname:
        await message.answer("Пожалуйста, сначала отправьте /start для регистрации.")
        return

    if user.base_daily_limit <= 0:
        await message.answer(
            "Лимит бюджета еще не настроен.\n"
            "Пожалуйста, выберите в меню Накопить на цель или Контролировать лимит."
        )
        return

    amount = None
    matched_category = match_category_keywords(message.text)

    # Если пользователь ввел короткую чистую цифру
    if message.text.strip().isdigit():
        try:
            amount = float(message.text.strip())
        except ValueError:
            pass

    # Если введена фраза — парсим через ИИ
    if amount is None or amount <= 0:
        processing_msg = await message.answer("Анализирую сообщение...")
        ai_data = parse_expense_with_ai(message.text)
        
        if ai_data and "amount" in ai_data and ai_data["amount"]:
            try:
                amt = float(ai_data["amount"])
                if amt > 0:
                    amount = amt
                    if ai_data.get("category"):
                        matched_category = ai_data.get("category")
            except (ValueError, TypeError):
                pass
        
        # Регулярный фоллбек: если ИИ не вернул сумму, извлекаем первое число
        if amount is None or amount <= 0:
            amount = extract_first_number(message.text)

        await processing_msg.delete()

    if not amount or amount <= 0:
        await message.answer(
            "Не удалось распознать сумму расхода.\n\n"
            "Напишите, например: 'Потратил 200 на воду' или просто отправьте сумму числом."
        )
        return

    # Если категория определена точно — сразу переходим к импульсивности!
    if matched_category and matched_category in EXPENSE_CATEGORIES:
        cat_idx = EXPENSE_CATEGORIES.index(matched_category)
        await message.answer(
            f"Сумма траты: {amount:,.0f} {CURRENCY_SYMBOL}\n"
            f"Категория: {matched_category}\n\n"
            f"Эта трата была запланирована или спонтанна?",
            reply_markup=get_impulsiveness_keyboard(cat_idx, amount)
        )
    else:
        # Если категория не определена — предлагаем кнопки категорий
        await message.answer(
            f"Сумма траты: {amount:,.0f} {CURRENCY_SYMBOL}\n\n"
            f"Шаг 1 из 2: Выберите категорию расходов:",
            reply_markup=get_categories_keyboard(amount)
        )


@router.callback_query(F.data.startswith("cat:"))
async def process_category_selected(callback: CallbackQuery):
    """Шаг 2: Фиксация категории и выбор импульсивности (без изменения баланса)."""
    parts = callback.data.split(":")
    cat_idx = int(parts[1])
    amount = float(parts[2])
    category_name = EXPENSE_CATEGORIES[cat_idx]

    await callback.message.edit_text(
        f"Сумма траты: {amount:,.0f} {CURRENCY_SYMBOL}\n"
        f"Категория: {category_name}\n\n"
        f"Шаг 2 из 2: Эта трата была запланирована или спонтанна?",
        reply_markup=get_impulsiveness_keyboard(cat_idx, amount)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("imp:"))
async def process_impulsiveness_selected(callback: CallbackQuery):
    """
    Шаг 3: Финальное сохранение расхода, динамический пересчет и логика Тамагочи.
    Финансовый алгоритм и прибавление суммы срабатывают СТРОГО ОДИН РАЗ здесь!
    """
    parts = callback.data.split(":")
    imp_type = parts[1]  # "planned" или "spontaneous"
    cat_idx = int(parts[2])
    amount = float(parts[3])

    is_spontaneous = (imp_type == "spontaneous")
    expense_type_str = "Спонтанно" if is_spontaneous else "Планировал"
    category_name = EXPENSE_CATEGORIES[cat_idx]

    user_id = callback.from_user.id
    user = storage.get_user(user_id)
    if not user:
        await callback.message.edit_text("Пользователь не найден. Отправьте /start")
        await callback.answer()
        return

    # 1. Расчет финансового алгоритма (строго единожды)
    result = calculate_expense_impact(
        expense_amount=amount,
        is_spontaneous=is_spontaneous,
        base_daily_limit=user.base_daily_limit,
        current_daily_limit=user.current_daily_limit,
        weekly_living_budget=user.weekly_living_budget,
        today_spent_before=user.today_spent,
        week_spent_before=user.week_spent,
        week_spontaneous_before=user.week_spontaneous_spent,
        current_day_index=user.current_day_index,
        s_goal_weekly=user.weekly_goal_deposit,
        goal_cost=user.goal_cost,
        total_goal_shift_before=user.total_goal_shift_days
    )

    # 2. Обновление финансовых показателей
    user.today_spent = result.today_spent
    user.week_spent = result.week_spent
    user.week_spontaneous_spent = result.week_spontaneous_spent
    user.current_daily_limit = result.l_tomorrow
    user.total_goal_shift_days = result.total_goal_shift_days

    # 3. Логика Тамагочи:
    hp_loss = 0
    status_reasons = []

    if is_spontaneous:
        hp_loss += 15
        status_reasons.append("спонтанно: -15 HP")
    else:
        exp_gain = 10
        user.pet_exp += exp_gain
        if user.pet_exp >= 100:
            user.pet_level += 1
            user.pet_exp = user.pet_exp - 100
            user.pet_hp = min(100, user.pet_hp + 20)
            status_reasons.append("+10 EXP (Новый уровень!)")
        else:
            status_reasons.append("+10 EXP")

    # Потеря HP при перерасходе дневного лимита
    if result.overspend > 0:
        hp_loss += 10
        status_reasons.append("перерасход лимита: -10 HP")

    if hp_loss > 0:
        user.pet_hp = max(0, user.pet_hp - hp_loss)

    pet_status_change = ", ".join(status_reasons)

    # 4. Генерация ролевой реплики питомца через ИИ (Модель 2)
    pet_reply = generate_pet_response(
        category=category_name,
        amount=amount,
        is_spontaneous=is_spontaneous,
        current_hp=user.pet_hp,
        pet_level=user.pet_level,
        pet_name=user.pet_name
    )

    # 5. Сохранение профиля и запись в CSV
    storage.save_user(user)

    record = ExpenseRecord(
        nickname=user.nickname,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        amount=amount,
        category=category_name,
        expense_type=expense_type_str,
        current_daily_limit=result.limit_was,
        goal_shift_days=result.goal_shift_days
    )
    storage.log_expense(record)

    # 6. Формирование структурированного ответа с пустыми строками и разделителями
    overspend_text = f"Перерасход: {result.overspend:,.0f} {CURRENCY_SYMBOL}" if result.overspend > 0 else "В пределах лимита"
    
    hp_bar = render_progress_bar(user.pet_hp, 100, 10)
    exp_bar = render_progress_bar(user.pet_exp, 100, 10)

    msg_lines = [
        "Учет траты выполнен",
        "────────────────────",
        f"Сумма: {amount:,.0f} {CURRENCY_SYMBOL} ({category_name}, {expense_type_str})",
        f"Сегодня потрачено: {result.today_spent:,.0f} {CURRENCY_SYMBOL} (Лимит был: {result.limit_was:,.0f} {CURRENCY_SYMBOL}, {overspend_text})",
        f"Новый дневной лимит на завтра: {result.l_tomorrow:,.0f} {CURRENCY_SYMBOL}",
        "",
        "────────────────────",
        f"Питомец {user.pet_name} [Уровень {user.pet_level}]",
        f"HP: {hp_bar} {user.pet_hp}/100",
        f"EXP: {exp_bar} {user.pet_exp}/100",
        f"Изменения: {pet_status_change}",
        "",
        f"«{pet_reply}»"
    ]

    if user.mode == "GOAL" and user.goal_name:
        shift_delta_text = f"+{result.goal_shift_days} дн." if result.goal_shift_days > 0 else "0 дн. (по графику)"
        msg_lines.append(
            f"\n────────────────────\n"
            f"Цель {user.goal_name}: {shift_delta_text} (Осталось накопить: {result.remaining_goal_amount:,.0f} {CURRENCY_SYMBOL})"
        )

    if is_spontaneous or result.week_spontaneous_spent > 0:
        msg_lines.append(
            f"\nСпонтанные покупки на этой неделе: {result.week_spontaneous_spent:,.0f} {CURRENCY_SYMBOL}"
        )

    response_text = "\n".join(msg_lines)

    await callback.message.edit_text(response_text)
    await callback.answer("Расход зафиксирован")