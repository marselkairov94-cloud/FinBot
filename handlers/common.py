from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database.storage import storage
from handlers.start import router as start_router, SetPetNameState
from config import CURRENCY_SYMBOL

router = Router()
router.include_router(start_router)


@router.message(F.text.in_(["Текущий статус", "Мой статус"]))
@router.message(Command("status"))
async def show_status(message: Message):
    """Отображение текущего финансового статуса."""
    user = storage.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала пройдите регистрацию по команде /start")
        return

    remaining_days = max(1, 7 - user.current_day_index)
    
    lines = [f"Финансовый профиль: {user.nickname}\n"]

    if user.mode == "GOAL" and user.goal_name:
        lines.append(f"Цель: {user.goal_name}")
        lines.append(f"Стоимость цели: {user.goal_cost:,.0f} {CURRENCY_SYMBOL}")
        lines.append(f"Срок: {user.goal_duration_weeks} нед. (~{round(user.goal_duration_weeks/4, 1)} мес.)")
        lines.append(f"Недельный доход: {user.weekly_income:,.0f} {CURRENCY_SYMBOL}")
        lines.append(f"Взнос в фонд цели в неделю: {user.weekly_goal_deposit:,.0f} {CURRENCY_SYMBOL}")
        lines.append(f"Бюджет на жизнь в неделю: {user.weekly_living_budget:,.0f} {CURRENCY_SYMBOL}\n")
    else:
        lines.append("Режим: Прямой контроль лимита\n")

    lines.append(f"Текущий день недели: {user.current_day_index} из 7 (осталось {remaining_days} дн.)")
    lines.append(f"Базовый дневной лимит: {user.base_daily_limit:,.0f} {CURRENCY_SYMBOL} в день")
    lines.append(f"Текущий дневной лимит: {user.current_daily_limit:,.0f} {CURRENCY_SYMBOL}\n")
    lines.append(f"Потрачено сегодня: {user.today_spent:,.0f} {CURRENCY_SYMBOL}")
    lines.append(f"Потрачено за неделю: {user.week_spent:,.0f} {CURRENCY_SYMBOL}\n")
    lines.append(f"Питомец {user.pet_name}: Уровень {user.pet_level} | HP {user.pet_hp}/100 | EXP {user.pet_exp}/100\n")
    lines.append("Для фиксации расхода отправьте сумму или текст в чат.")

    await message.answer("\n".join(lines))


@router.message(F.text.in_(["Сбросить настройки", "Сброс", "Reset", "reset"]))
@router.message(Command("reset"))
async def reset_profile(message: Message, state: FSMContext):
    """Сброс профиля пользователя."""
    await state.clear()
    storage.delete_user(message.from_user.id)
    await message.answer(
        "Профиль и настройки сброшены.\n"
        "Для нового запуска отправьте команду /start"
    )


@router.message(Command("help"))
async def show_help(message: Message):
    """Справочная информация."""
    help_text = (
        "Справка по FinBot\n\n"
        "Накопить на цель: выбор финансовой цели, расчет обязательного взноса и дневного лимита.\n\n"
        "Контролировать лимит: прямой ввод дневного или недельного бюджета.\n\n"
        "Фиксация расхода: отправьте боту число или текст (например: 'Потратил 200 на воду').\n\n"
        "/pet: карточка виртуального питомца Тамагочи.\n\n"
        "/stats: статистика расходов по категориям.\n\n"
        "/status: просмотр текущего баланса и лимита.\n\n"
        "/reset: сброс настроек и повторный выбор режима."
    )
    await message.answer(help_text)