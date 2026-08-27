import math
from dataclasses import dataclass
from typing import Optional
from config import MIN_REALISTIC_DAILY_LIMIT


@dataclass
class GoalCalculationResult:
    is_realistic: bool
    s_goal_weekly: float          # Обязательный взнос в фонд цели в неделю
    weekly_living_budget: float   # Доступный бюджет на жизнь в неделю
    daily_limit: float            # Базовый дневной лимит (L_day)
    total_expected_income: float  # Всего поступит средств за период
    realistic_duration_weeks: Optional[int] = None
    realistic_duration_months: Optional[float] = None
    warning_message: Optional[str] = None


@dataclass
class ExpenseCalculationResult:
    today_spent: float            # Суммарные траты за сегодня с учетом текущей
    week_spent: float             # Суммарные траты за неделю с учетом текущей
    limit_was: float
    overspend: float              # Delta = today_spent - limit_was
    l_tomorrow: float             # Новый дневной лимит на завтра
    goal_shift_days: int          # Сдвиг цели в днях из-за текущей траты/перерасхода
    total_goal_shift_days: int    # Суммарный сдвиг цели
    remaining_goal_amount: float  # Сколько осталось накопить (тенге)
    week_spontaneous_spent: float # Сумма спонтанных трат за неделю
    spontaneous_goal_shift_days: int  # Суммарный сдвиг из-за спонтанных трат


def calculate_goal_budget(
    goal_cost: float,
    duration_weeks: int,
    weekly_income: float
) -> GoalCalculationResult:
    """
    Математический расчет для сценария Накопить на цель.
    
    Формулы:
    Всего поступит = Недельный_Доход * Срок_в_неделях
    S_goal = Стоимость_цели / Срок_в_неделях
    Доступный бюджет на жизнь = Недельный_Доход - S_goal
    L_day = Доступный бюджет на жизнь / 7
    """
    total_income = weekly_income * duration_weeks
    s_goal = goal_cost / duration_weeks if duration_weeks > 0 else goal_cost
    weekly_living_budget = weekly_income - s_goal
    daily_limit = weekly_living_budget / 7.0

    if daily_limit < MIN_REALISTIC_DAILY_LIMIT or weekly_living_budget <= 0:
        min_living_budget_week = MIN_REALISTIC_DAILY_LIMIT * 7.0  # 700 ₸/нед
        
        if weekly_income > min_living_budget_week:
            max_s_goal_allowed = weekly_income - min_living_budget_week
            realistic_weeks = math.ceil(goal_cost / max_s_goal_allowed)
        else:
            safe_savings_week = max(100.0, weekly_income * 0.5)
            realistic_weeks = math.ceil(goal_cost / safe_savings_week)

        realistic_months = round(realistic_weeks / 4.0, 1)
        duration_months = round(duration_weeks / 4.0, 1)

        warning = (
            f"При таком доходе ({weekly_income:,.0f} ₸ в неделю) накопить за {duration_months} мес. "
            f"({duration_weeks} нед.) не получится: лимит {max(0.0, daily_limit):.1f} ₸ в день слишком мал.\n\n"
            f"Реалистичный срок накопления: около {realistic_months} мес. ({realistic_weeks} нед.)."
        )
        return GoalCalculationResult(
            is_realistic=False,
            s_goal_weekly=s_goal,
            weekly_living_budget=weekly_living_budget,
            daily_limit=max(0.0, daily_limit),
            total_expected_income=total_income,
            realistic_duration_weeks=realistic_weeks,
            realistic_duration_months=realistic_months,
            warning_message=warning
        )

    return GoalCalculationResult(
        is_realistic=True,
        s_goal_weekly=s_goal,
        weekly_living_budget=weekly_living_budget,
        daily_limit=daily_limit,
        total_expected_income=total_income
    )


def calculate_expense_impact(
    expense_amount: float,
    is_spontaneous: bool,
    base_daily_limit: float,
    current_daily_limit: float,
    weekly_living_budget: float,
    today_spent_before: float,
    week_spent_before: float,
    week_spontaneous_before: float,
    current_day_index: int,       # 1..7
    s_goal_weekly: float,
    goal_cost: float,
    total_goal_shift_before: int
) -> ExpenseCalculationResult:
    """
    Предиктивный алгоритм и динамический пересчет расходов.
    Суммирование происходит строго один раз внутри этой функции.
    """
    today_spent_now = today_spent_before + expense_amount
    week_spent_now = week_spent_before + expense_amount
    week_spontaneous_now = week_spontaneous_before + (expense_amount if is_spontaneous else 0.0)

    limit_was = current_daily_limit if current_daily_limit > 0 else base_daily_limit
    overspend = max(0.0, today_spent_now - limit_was)

    remaining_days_in_week = max(1, 7 - current_day_index)
    remaining_weekly_budget = weekly_living_budget - week_spent_now
    if remaining_days_in_week > 0:
        l_tomorrow = max(0.0, remaining_weekly_budget / remaining_days_in_week)
    else:
        l_tomorrow = base_daily_limit

    goal_shift_days = 0
    if s_goal_weekly > 0:
        daily_goal_rate = s_goal_weekly / 7.0
        if overspend > 0 and daily_goal_rate > 0:
            goal_shift_days = math.ceil(overspend / daily_goal_rate)
        
        spontaneous_goal_shift_days = (
            math.ceil(week_spontaneous_now / daily_goal_rate) if daily_goal_rate > 0 else 0
        )
    else:
        spontaneous_goal_shift_days = 0

    total_goal_shift_now = total_goal_shift_before + goal_shift_days
    remaining_goal_amount = max(0.0, goal_cost)

    return ExpenseCalculationResult(
        today_spent=today_spent_now,
        week_spent=week_spent_now,
        limit_was=limit_was,
        overspend=overspend,
        l_tomorrow=l_tomorrow,
        goal_shift_days=goal_shift_days,
        total_goal_shift_days=total_goal_shift_now,
        remaining_goal_amount=remaining_goal_amount,
        week_spontaneous_spent=week_spontaneous_now,
        spontaneous_goal_shift_days=spontaneous_goal_shift_days
    )
