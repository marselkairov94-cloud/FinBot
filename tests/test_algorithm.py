import math
import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.algorithm import (
    calculate_goal_budget,
    calculate_expense_impact,
    GoalCalculationResult,
    ExpenseCalculationResult
)
from database.models import ExpenseRecord, UserProfile
from database.storage import Storage, storage
from handlers.goal_onboarding import parse_duration_to_weeks
from handlers.expenses import extract_first_number, render_progress_bar
from ai_helper import generate_pet_response, match_category_keywords


def test_calculate_goal_budget_realistic():
    """Тест реалистичной цели: Наушники 25000 ₸ за 8 недель при доходе 5000 ₸/нед."""
    res = calculate_goal_budget(
        goal_cost=25000.0,
        duration_weeks=8,
        weekly_income=5000.0
    )
    assert res.is_realistic is True
    assert res.s_goal_weekly == 25000.0 / 8.0  # 3125 ₸
    assert res.weekly_living_budget == 5000.0 - 3125.0  # 1875 ₸
    assert math.isclose(res.daily_limit, 1875.0 / 7.0, rel_tol=1e-3)
    assert res.total_expected_income == 40000.0


def test_calculate_goal_budget_unrealistic():
    """Тест нереалистичной цели: Наушники 25000 ₸ за 2 недели при доходе 5000 ₸/нед."""
    res = calculate_goal_budget(
        goal_cost=25000.0,
        duration_weeks=2,
        weekly_income=5000.0
    )
    assert res.is_realistic is False
    assert res.warning_message is not None
    assert res.realistic_duration_weeks is not None
    assert res.realistic_duration_weeks > 2


def test_calculate_expense_impact_no_overspend():
    """Тест расхода в пределах лимита."""
    res = calculate_expense_impact(
        expense_amount=200.0,
        is_spontaneous=False,
        base_daily_limit=300.0,
        current_daily_limit=300.0,
        weekly_living_budget=2100.0,
        today_spent_before=0.0,
        week_spent_before=0.0,
        week_spontaneous_before=0.0,
        current_day_index=1,
        s_goal_weekly=3500.0,
        goal_cost=25000.0,
        total_goal_shift_before=0
    )
    assert res.today_spent == 200.0
    assert res.week_spent == 200.0
    assert res.overspend == 0.0
    assert res.goal_shift_days == 0
    assert math.isclose(res.l_tomorrow, 1900.0 / 6.0, rel_tol=1e-3)


def test_sequential_expenses_summation():
    """Тест последовательного сложения расходов (450 + 350 = 800 ₸, без двойного счета)."""
    # Первая трата 450 ₸
    res1 = calculate_expense_impact(
        expense_amount=450.0,
        is_spontaneous=False,
        base_daily_limit=500.0,
        current_daily_limit=500.0,
        weekly_living_budget=3500.0,
        today_spent_before=0.0,
        week_spent_before=0.0,
        week_spontaneous_before=0.0,
        current_day_index=1,
        s_goal_weekly=0.0,
        goal_cost=0.0,
        total_goal_shift_before=0
    )
    assert res1.today_spent == 450.0
    assert res1.week_spent == 450.0
    assert res1.overspend == 0.0

    # Вторая трата 350 ₸ (лимит 500 ₸, суммарно 800 ₸ -> перерасход 300 ₸)
    res2 = calculate_expense_impact(
        expense_amount=350.0,
        is_spontaneous=False,
        base_daily_limit=500.0,
        current_daily_limit=500.0,
        weekly_living_budget=3500.0,
        today_spent_before=res1.today_spent,
        week_spent_before=res1.week_spent,
        week_spontaneous_before=res1.week_spontaneous_spent,
        current_day_index=1,
        s_goal_weekly=0.0,
        goal_cost=0.0,
        total_goal_shift_before=0
    )
    assert res2.today_spent == 800.0  # Не 1150!
    assert res2.week_spent == 800.0   # Не 1150!
    assert res2.overspend == 300.0


def test_calculate_expense_impact_with_overspend_and_shift():
    """Тест расхода с перерасходом и предиктивным сдвигом цели."""
    res = calculate_expense_impact(
        expense_amount=800.0,
        is_spontaneous=True,
        base_daily_limit=300.0,
        current_daily_limit=300.0,
        weekly_living_budget=2100.0,
        today_spent_before=0.0,
        week_spent_before=0.0,
        week_spontaneous_before=0.0,
        current_day_index=1,
        s_goal_weekly=3500.0,
        goal_cost=25000.0,
        total_goal_shift_before=0
    )
    assert res.today_spent == 800.0
    assert res.week_spent == 800.0
    assert res.overspend == 500.0
    assert res.goal_shift_days == 1
    assert res.week_spontaneous_spent == 800.0
    assert res.spontaneous_goal_shift_days >= 1


def test_parse_duration_to_weeks():
    """Тест парсера сроков."""
    assert parse_duration_to_weeks("2 месяца") == 8
    assert parse_duration_to_weeks("2 мес") == 8
    assert parse_duration_to_weeks("8 недель") == 8
    assert parse_duration_to_weeks("12 нед") == 12
    assert parse_duration_to_weeks("1 год") == 52


def test_extract_first_number():
    """Тест умного извлечения чисел из свободного текста."""
    assert extract_first_number("Потратил 10 тг на еду") == 10.0
    assert extract_first_number("Потратил 1200 на еду") == 1200.0
    assert extract_first_number("Купил наушники за 25 000 тенге") == 25000.0
    assert extract_first_number("Шаурма 1500тг") == 1500.0
    assert extract_first_number("120.50") == 120.5
    assert extract_first_number("Текст без чисел") is None


def test_match_category_keywords():
    """Тест точного сопоставления ключевых слов категорий."""
    assert match_category_keywords("потратил 200 на воду") == "Еда и фастфуд"
    assert match_category_keywords("такси до дома 1500") == "Транспорт"
    assert match_category_keywords("купил кроссовки на вб") == "Маркетплейсы"
    assert match_category_keywords("подписка на spotify") == "Игры и подписки"
    assert match_category_keywords("купил лекарства в аптеке") == "Другое"
    assert match_category_keywords("просто текст 500") is None


def test_render_progress_bar():
    """Тест генератора шкал прогресса."""
    bar_full = render_progress_bar(100, 100, 10)
    assert bar_full == "[██████████]"
    bar_half = render_progress_bar(50, 100, 10)
    assert bar_half == "[█████░░░░░]"
    bar_zero = render_progress_bar(0, 100, 10)
    assert bar_zero == "[░░░░░░░░░░]"


def test_user_profile_tamagotchi():
    """Тест профиля пользователя и полей Тамагочи с именем по умолчанию."""
    user = UserProfile(user_id=123, nickname="Alex")
    assert user.nickname == "Alex"
    assert user.pet_name == "Тамагочи"
    assert user.pet_hp == 100
    assert user.pet_exp == 0
    assert user.pet_level == 1
    
    d = user.to_dict()
    assert d["pet_hp"] == 100
    user_restored = UserProfile.from_dict(d)
    assert user_restored.pet_name == "Тамагочи"
    assert user_restored.pet_hp == 100
    assert user_restored.pet_level == 1


def test_storage_get_user_expenses():
    """Тест сохранения и чтения расходов пользователя из CSV."""
    rec = ExpenseRecord(
        nickname="Tester",
        timestamp="2026-08-25 12:00:00",
        amount=1500.0,
        category="Еда и фастфуд",
        expense_type="Планировал",
        current_daily_limit=500.0,
        goal_shift_days=0
    )
    storage.log_expense(rec)
    expenses = storage.get_user_expenses("Tester")
    assert len(expenses) >= 1
    assert expenses[-1].nickname == "Tester"
    assert expenses[-1].amount == 1500.0


def test_pet_response_fallback():
    """Тест фоллбек-ответов питомца."""
    rep_spont = generate_pet_response("Еда и фастфуд", 1000.0, is_spontaneous=True, current_hp=50)
    assert isinstance(rep_spont, str) and len(rep_spont) > 5

    rep_plan = generate_pet_response("Транспорт", 500.0, is_spontaneous=False, current_hp=100)
    assert isinstance(rep_plan, str) and len(rep_plan) > 5


if __name__ == "__main__":
    pytest.main(["-v", __file__])
