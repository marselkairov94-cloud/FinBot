from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.storage import storage
from database.models import UserProfile
from keyboards.reply import get_main_menu_keyboard
from keyboards.inline import get_limit_type_keyboard
from config import CURRENCY_SYMBOL

router = Router()

class LimitStates(StatesGroup):
    waiting_for_type_choice = State()
    waiting_for_daily_amount = State()
    waiting_for_weekly_amount = State()

@router.message(F.text.contains("онтролировать"))
async def start_limit_onboarding(message: Message, state: FSMContext):
    user = storage.get_user(message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, сначала отправьте команду /start для регистрации.")
        return

    await state.set_state(LimitStates.waiting_for_type_choice)
    await message.answer(
        "Сценарий: Контроль лимита (без накопления)\n\n"
        "Этот режим подходит, если у вас пока нет конкретной цели.\n\n"
        "Выберите формат задания лимита:",
        reply_markup=get_limit_type_keyboard()
    )

@router.callback_query(F.data == "limit_type:daily")
async def process_daily_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LimitStates.waiting_for_daily_amount)
    await callback.message.edit_text(
        "Введите желаемый дневной лимит в тенге (например: 2000):"
    )
    await callback.answer()

@router.callback_query(F.data == "limit_type:weekly")
async def process_weekly_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LimitStates.waiting_for_weekly_amount)
    await callback.message.edit_text(
        "Введите желаемый недельный бюджет в тенге (например: 14000):"
    )
    await callback.answer()

@router.message(LimitStates.waiting_for_daily_amount)
async def process_daily_amount(message: Message, state: FSMContext):
    try:
        daily_limit = float(message.text.replace(" ", "").replace(",", "."))
        if daily_limit <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число (например: 2000):")
        return

    user_id = message.from_user.id
    user = storage.get_user(user_id) or UserProfile(user_id=user_id, nickname=message.from_user.username or str(user_id))

    user.mode = "LIMIT_ONLY"
    user.goal_name = None
    user.goal_cost = 0.0
    user.goal_duration_weeks = 0
    user.weekly_income = daily_limit * 7.0
    user.weekly_goal_deposit = 0.0
    user.weekly_living_budget = daily_limit * 7.0
    user.base_daily_limit = daily_limit
    user.current_daily_limit = daily_limit
    user.today_spent = 0.0
    user.week_spent = 0.0
    user.week_spontaneous_spent = 0.0
    user.total_goal_shift_days = 0

    storage.save_user(user)
    await state.clear()

    lines = [
        f"Дневной лимит установлен: {daily_limit:,.0f} {CURRENCY_SYMBOL} в день",
        f"Эквивалент на неделю: {daily_limit * 7:,.0f} {CURRENCY_SYMBOL}\n",
        "Для фиксации расходов отправляйте сумму траты числом в чат."
    ]
    await message.answer("\n".join(lines), reply_markup=get_main_menu_keyboard())

@router.message(LimitStates.waiting_for_weekly_amount)
async def process_weekly_amount(message: Message, state: FSMContext):
    try:
        weekly_budget = float(message.text.replace(" ", "").replace(",", "."))
        if weekly_budget <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число (например: 14000):")
        return

    daily_limit = weekly_budget / 7.0
    user_id = message.from_user.id
    user = storage.get_user(user_id) or UserProfile(user_id=user_id, nickname=message.from_user.username or str(user_id))

    user.mode = "LIMIT_ONLY"
    user.goal_name = None
    user.goal_cost = 0.0
    user.goal_duration_weeks = 0
    user.weekly_income = weekly_budget
    user.weekly_goal_deposit = 0.0
    user.weekly_living_budget = weekly_budget
    user.base_daily_limit = daily_limit
    user.current_daily_limit = daily_limit
    user.today_spent = 0.0
    user.week_spent = 0.0
    user.week_spontaneous_spent = 0.0
    user.total_goal_shift_days = 0

    storage.save_user(user)
    await state.clear()

    lines = [
        f"Недельный бюджет установлен: {weekly_budget:,.0f} {CURRENCY_SYMBOL}",
        f"Рассчитанный дневной лимит: {daily_limit:,.0f} {CURRENCY_SYMBOL} в день\n",
        "Для фиксации расходов отправляйте сумму траты числом в чат."
    ]
    await message.answer("\n".join(lines), reply_markup=get_main_menu_keyboard())