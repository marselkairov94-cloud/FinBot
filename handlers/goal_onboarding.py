import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.storage import storage
from database.models import UserProfile
from services.algorithm import calculate_goal_budget
from keyboards.reply import get_main_menu_keyboard
from keyboards.inline import get_reality_fix_keyboard
from config import CURRENCY_SYMBOL

router = Router()

# Минимальный порог дневного лимита (можно менять)
MIN_DAILY_LIMIT = 1000

class GoalStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_cost = State()
    waiting_for_duration = State()
    waiting_for_income = State()
    waiting_for_custom_duration = State()

def parse_duration_to_weeks(text: str) -> int:
    text_clean = text.lower().strip()
    match = re.search(r"(\d+(?:[.,]\d+)?)", text_clean)
    if not match:
        return 0

    val = float(match.group(1).replace(",", "."))
    if "мес" in text_clean:
        return max(1, int(round(val * 4)))
    elif "год" in text_clean or "лет" in text_clean:
        return max(1, int(round(val * 52)))
    elif "дн" in text_clean or "ден" in text_clean:
        return max(1, int(round(val / 7)))
    else:
        if val <= 12 and ("нед" not in text_clean):
            return max(1, int(round(val * 4)))
        return max(1, int(round(val)))

@router.message(F.text.contains("акопить"))
async def start_goal_onboarding(message: Message, state: FSMContext):
    user = storage.get_user(message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, сначала отправьте команду /start для регистрации.")
        return

    await state.set_state(GoalStates.waiting_for_name)
    await message.answer(
        "Сценарий: Накопить на цель\n\n"
        "Какая у вас финансовая цель?\n"
        "Напишите название (например: Наушники, Кроссовки, Планшет):"
    )

@router.message(GoalStates.waiting_for_name)
async def process_goal_name(message: Message, state: FSMContext):
    goal_name = message.text.strip()
    if len(goal_name) < 2:
        await message.answer("Пожалуйста, введите корректное название цели:")
        return

    await state.update_data(goal_name=goal_name)
    await state.set_state(GoalStates.waiting_for_cost)
    await message.answer(
        f"Цель: {goal_name}\n\n"
        f"Сколько стоит эта цель в тенге?\n"
        f"Введите число (например: 25000):"
    )

@router.message(GoalStates.waiting_for_cost)
async def process_goal_cost(message: Message, state: FSMContext):
    try:
        cost = float(message.text.replace(" ", "").replace(",", "."))
        if cost <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число (например: 25000):")
        return

    await state.update_data(goal_cost=cost)
    await state.set_state(GoalStates.waiting_for_duration)
    await message.answer(
        f"Стоимость: {cost:,.0f} {CURRENCY_SYMBOL}\n\n"
        f"За какой срок вы хотите накопить?\n"
        f"Введите срок в месяцах или неделях (например: 2 месяца или 8 недель):"
    )

@router.message(GoalStates.waiting_for_duration)
async def process_goal_duration(message: Message, state: FSMContext):
    weeks = parse_duration_to_weeks(message.text)
    if weeks <= 0:
        await message.answer("Не удалось распознать срок. Введите, например: 2 месяца или 8 недель:")
        return

    await state.update_data(goal_duration_weeks=weeks)
    await state.set_state(GoalStates.waiting_for_income)
    await message.answer(
        f"Срок: {weeks} нед. (~{round(weeks / 4, 1)} мес.)\n\n"
        f"Какой ваш средний недельный доход в тенге?\n"
        f"Введите число (например: 5000):"
    )

@router.message(GoalStates.waiting_for_income)
async def process_goal_income(message: Message, state: FSMContext):
    try:
        income = float(message.text.replace(" ", "").replace(",", "."))
        if income <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число дохода (например: 5000):")
        return

    data = await state.get_data()
    goal_name = data["goal_name"]
    goal_cost = data["goal_cost"]
    duration_weeks = data["goal_duration_weeks"]

    calc = calculate_goal_budget(
        goal_cost=goal_cost,
        duration_weeks=duration_weeks,
        weekly_income=income
    )

    if not calc.is_realistic:
        await state.update_data(weekly_income=income, realistic_weeks=calc.realistic_duration_weeks)
        await message.answer(
            f"{calc.warning_message}\n\n"
            f"Выберите действие:",
            reply_markup=get_reality_fix_keyboard(calc.realistic_duration_weeks or 12)
        )
        return

    # Проверка на слишком маленький лимит
    if calc.daily_limit < MIN_DAILY_LIMIT:
        await state.update_data(weekly_income=income)
        builder = InlineKeyboardBuilder()
        builder.button(text="Изменить срок накопления", callback_data="adjust_limit:duration")
        builder.button(text="Оставить как есть", callback_data="adjust_limit:ignore")
        builder.adjust(1)
        
        await message.answer(
            f"Внимание: расчетный дневной лимит получился очень маленьким: {calc.daily_limit:,.0f} {CURRENCY_SYMBOL}.\n"
            f"Вам будет сложно укладываться в эту сумму каждый день.\n\n"
            f"Хотите увеличить срок накопления, чтобы повысить ежедневный лимит на жизнь?",
            reply_markup=builder.as_markup()
        )
        return

    await _save_and_confirm_goal(
        message=message,
        state=state,
        user_id=message.from_user.id,
        goal_name=goal_name,
        goal_cost=goal_cost,
        duration_weeks=duration_weeks,
        weekly_income=income,
        calc=calc
    )

@router.callback_query(F.data.startswith("adjust_limit:"))
async def process_limit_adjustment(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    data = await state.get_data()
    
    if action == "ignore":
        goal_cost = data["goal_cost"]
        duration_weeks = data["goal_duration_weeks"]
        weekly_income = data["weekly_income"]
        calc = calculate_goal_budget(goal_cost=goal_cost, duration_weeks=duration_weeks, weekly_income=weekly_income)
        await _save_and_confirm_goal(
            message=callback.message,
            state=state,
            user_id=callback.from_user.id,
            goal_name=data["goal_name"],
            goal_cost=goal_cost,
            duration_weeks=duration_weeks,
            weekly_income=weekly_income,
            calc=calc,
            is_edit=True
        )
        await callback.answer("Лимит сохранен без изменений")
    elif action == "duration":
        await state.set_state(GoalStates.waiting_for_custom_duration)
        await callback.message.edit_text("Введите новый желаемый срок накопления (например: 6 месяцев или 24 недели):")
        await callback.answer()

@router.callback_query(F.data.startswith("fix_goal_weeks:"))
async def process_fix_goal_callback(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    data = await state.get_data()

    if action == "custom":
        await state.set_state(GoalStates.waiting_for_custom_duration)
        await callback.message.edit_text(
            "Введите новый желаемый срок накопления (например: 6 месяцев или 24 недели):"
        )
        await callback.answer()
        return

    new_weeks = int(action)
    goal_name = data.get("goal_name", "Цель")
    goal_cost = data.get("goal_cost", 25000.0)
    weekly_income = data.get("weekly_income", 5000.0)

    calc = calculate_goal_budget(
        goal_cost=goal_cost,
        duration_weeks=new_weeks,
        weekly_income=weekly_income
    )

    if calc.daily_limit < MIN_DAILY_LIMIT:
        await state.update_data(goal_duration_weeks=new_weeks)
        builder = InlineKeyboardBuilder()
        builder.button(text="Изменить срок накопления", callback_data="adjust_limit:duration")
        builder.button(text="Оставить как есть", callback_data="adjust_limit:ignore")
        builder.adjust(1)
        
        await callback.message.edit_text(
            f"Новый дневной лимит все еще очень мал: {calc.daily_limit:,.0f} {CURRENCY_SYMBOL}.\n"
            f"Хотите еще увеличить срок?",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    await _save_and_confirm_goal(
        message=callback.message,
        state=state,
        user_id=callback.from_user.id,
        goal_name=goal_name,
        goal_cost=goal_cost,
        duration_weeks=new_weeks,
        weekly_income=weekly_income,
        calc=calc,
        is_edit=True
    )
    await callback.answer("Срок скорректирован")

@router.message(GoalStates.waiting_for_custom_duration)
async def process_custom_duration(message: Message, state: FSMContext):
    weeks = parse_duration_to_weeks(message.text)
    if weeks <= 0:
        await message.answer("Не удалось распознать срок. Введите, например: 6 месяцев или 24 недели:")
        return

    data = await state.get_data()
    goal_name = data["goal_name"]
    goal_cost = data["goal_cost"]
    weekly_income = data["weekly_income"]

    calc = calculate_goal_budget(
        goal_cost=goal_cost,
        duration_weeks=weeks,
        weekly_income=weekly_income
    )

    if calc.daily_limit < MIN_DAILY_LIMIT:
        await state.update_data(goal_duration_weeks=weeks)
        builder = InlineKeyboardBuilder()
        builder.button(text="Изменить срок накопления", callback_data="adjust_limit:duration")
        builder.button(text="Оставить как есть", callback_data="adjust_limit:ignore")
        builder.adjust(1)
        
        await message.answer(
            f"Расчетный дневной лимит снова получился маленьким: {calc.daily_limit:,.0f} {CURRENCY_SYMBOL}.\n"
            f"Хотите еще увеличить срок?",
            reply_markup=builder.as_markup()
        )
        return

    await _save_and_confirm_goal(
        message=message,
        state=state,
        user_id=message.from_user.id,
        goal_name=goal_name,
        goal_cost=goal_cost,
        duration_weeks=weeks,
        weekly_income=weekly_income,
        calc=calc
    )

async def _save_and_confirm_goal(
    message: Message,
    state: FSMContext,
    user_id: int,
    goal_name: str,
    goal_cost: float,
    duration_weeks: int,
    weekly_income: float,
    calc,
    is_edit: bool = False
):
    user = storage.get_user(user_id) or UserProfile(user_id=user_id, nickname=message.from_user.username or str(user_id))
    
    user.mode = "GOAL"
    user.goal_name = goal_name
    user.goal_cost = goal_cost
    user.goal_duration_weeks = duration_weeks
    user.weekly_income = weekly_income
    user.weekly_goal_deposit = calc.s_goal_weekly
    user.weekly_living_budget = calc.weekly_living_budget
    user.base_daily_limit = calc.daily_limit
    user.current_daily_limit = calc.daily_limit
    user.today_spent = 0.0
    user.week_spent = 0.0
    user.week_spontaneous_spent = 0.0
    user.total_goal_shift_days = 0

    storage.save_user(user)
    await state.clear()

    lines = [
        f"Финансовая цель '{goal_name}' успешно настроена.\n",
        "Расчет бюджета:",
        f"Стоимость цели: {goal_cost:,.0f} {CURRENCY_SYMBOL}",
        f"Срок накопления: {duration_weeks} нед. (~{round(duration_weeks/4, 1)} мес.)",
        f"Обязательный взнос в фонд в неделю: {calc.s_goal_weekly:,.0f} {CURRENCY_SYMBOL}",
        f"Доступный бюджет на жизнь: {calc.weekly_living_budget:,.0f} {CURRENCY_SYMBOL} в неделю",
        f"Базовый дневной лимит: {calc.daily_limit:,.0f} {CURRENCY_SYMBOL} в день\n",
        "Для учета расходов отправляйте сумму траты числом в чат."
    ]
    text = "\n".join(lines)

    if is_edit:
        await message.edit_text(text)
        await message.answer("Главное меню обновлено.", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer(text, reply_markup=get_main_menu_keyboard())