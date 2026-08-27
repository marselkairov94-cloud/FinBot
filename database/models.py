from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from datetime import datetime


@dataclass
class ExpenseRecord:
    nickname: str
    timestamp: str
    amount: float
    category: str
    expense_type: str  # "Планировал" или "Спонтанно"
    current_daily_limit: float
    goal_shift_days: int

    def to_csv_row(self) -> list:
        return [
            self.nickname,
            self.timestamp,
            f"{self.amount:.2f}",
            self.category,
            self.expense_type,
            f"{self.current_daily_limit:.2f}",
            str(self.goal_shift_days)
        ]

    @classmethod
    def from_csv_row(cls, row: list) -> "ExpenseRecord":
        return cls(
            nickname=row[0],
            timestamp=row[1],
            amount=float(row[2]),
            category=row[3],
            expense_type=row[4],
            current_daily_limit=float(row[5]) if len(row) > 5 else 0.0,
            goal_shift_days=int(row[6]) if len(row) > 6 else 0
        )


@dataclass
class UserProfile:
    user_id: int
    nickname: str
    mode: Literal["GOAL", "LIMIT_ONLY"] = "GOAL"
    
    # Параметры цели (для режима GOAL)
    goal_name: Optional[str] = None
    goal_cost: float = 0.0
    goal_duration_weeks: int = 0
    weekly_income: float = 0.0
    weekly_goal_deposit: float = 0.0  # S_goal = goal_cost / goal_duration_weeks
    weekly_living_budget: float = 0.0  # weekly_income - weekly_goal_deposit
    
    # Лимиты
    base_daily_limit: float = 0.0  # L_day
    current_daily_limit: float = 0.0  # Динамический лимит на сегодня/завтра
    
    # Текущее отслеживание периода (неделя)
    week_start_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    current_day_index: int = 1  # 1..7 (день текущей недели)
    today_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    # Накопленные траты
    today_spent: float = 0.0
    week_spent: float = 0.0
    week_spontaneous_spent: float = 0.0
    
    # Накопительный сдвиг цели в днях
    total_goal_shift_days: int = 0

    # Параметры Тамагочи
    pet_name: str = "Тамагочи"
    pet_hp: int = 100        # Здоровье (0-100)
    pet_exp: int = 0         # Опыт (0-100)
    pet_level: int = 1       # Уровень
    
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        # Поддержка обратной совместимости для старых записей
        if "participant_id" in data and "nickname" not in data:
            data["nickname"] = data.pop("participant_id")
            
        data.setdefault("pet_name", "Тамагочи")
        data.setdefault("pet_hp", 100)
        data.setdefault("pet_exp", 0)
        data.setdefault("pet_level", 1)
        
        return cls(**data)
