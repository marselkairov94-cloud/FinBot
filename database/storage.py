import os
import csv
import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from config import EXPENSES_CSV, DATA_DIR
from database.models import UserProfile, ExpenseRecord

USERS_JSON = DATA_DIR / "users_profiles.json"
CSV_HEADER = [
    "Никнейм",
    "Дата_Время",
    "Сумма",
    "Категория",
    "Тип_Траты",
    "Текущий_Дневной_Лимит",
    "Сдвиг_Цели_Дней"
]


class Storage:
    def __init__(self):
        self._profiles: Dict[int, UserProfile] = {}
        self._init_csv()
        self._load_profiles()

    def _init_csv(self) -> None:
        """Создает файл CSV с заголовками, если он еще не существует."""
        if not EXPENSES_CSV.exists() or EXPENSES_CSV.stat().st_size == 0:
            with open(EXPENSES_CSV, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADER)

    def _load_profiles(self) -> None:
        """Загружает профили пользователей из JSON."""
        if USERS_JSON.exists():
            try:
                with open(USERS_JSON, mode="r", encoding="utf-8") as f:
                    data = json.load(f)
                    for uid_str, udata in data.items():
                        self._profiles[int(uid_str)] = UserProfile.from_dict(udata)
            except Exception as e:
                print(f"[Storage] Ошибка загрузки профилей: {e}")

    def _save_profiles(self) -> None:
        """Сохраняет профили пользователей в JSON."""
        try:
            with open(USERS_JSON, mode="w", encoding="utf-8") as f:
                data = {str(k): v.to_dict() for k, v in self._profiles.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Storage] Ошибка сохранения профилей: {e}")

    def get_user(self, user_id: int) -> Optional[UserProfile]:
        """Возвращает профиль пользователя, обновляя состояние дня/недели при необходимости."""
        user = self._profiles.get(user_id)
        if user:
            self._check_date_rollover(user)
        return user

    def get_user_by_telegram_id(self, user_id: int) -> Optional[UserProfile]:
        """Алиас для get_user."""
        return self.get_user(user_id)

    def save_user(self, user: UserProfile) -> None:
        """Сохраняет или обновляет профиль пользователя."""
        self._profiles[user.user_id] = user
        self._save_profiles()

    def delete_user(self, user_id: int) -> None:
        """Удаляет профиль пользователя (для сброса/рестарта)."""
        if user_id in self._profiles:
            del self._profiles[user_id]
            self._save_profiles()

    def log_expense(self, record: ExpenseRecord) -> None:
        """Логирует запись о расходе в expenses_dataset.csv."""
        self._init_csv()
        with open(EXPENSES_CSV, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(record.to_csv_row())

    def get_user_expenses(self, nickname: str) -> List[ExpenseRecord]:
        """Вычитывает все расходы конкретного пользователя из CSV для /stats."""
        self._init_csv()
        expenses: List[ExpenseRecord] = []
        if not EXPENSES_CSV.exists():
            return expenses

        try:
            with open(EXPENSES_CSV, mode="r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if not row or len(row) < 5:
                        continue
                    # row[0] - никнейм
                    if row[0].strip().lower() == nickname.strip().lower():
                        try:
                            record = ExpenseRecord.from_csv_row(row)
                            expenses.append(record)
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            print(f"[Storage] Ошибка чтения расходов из CSV: {e}")

        return expenses

    def _check_date_rollover(self, user: UserProfile) -> None:
        """Проверяет смену календарного дня и недели для адаптивного учета."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        if user.today_date != today_str:
            try:
                prev_date = datetime.strptime(user.today_date, "%Y-%m-%d")
                curr_date = datetime.strptime(today_str, "%Y-%m-%d")
                delta_days = (curr_date - prev_date).days
            except Exception:
                delta_days = 1

            user.today_date = today_str
            user.today_spent = 0.0

            # Продвижение дня недели (1..7)
            new_day_idx = user.current_day_index + delta_days
            if new_day_idx > 7:
                # Новая неделя
                user.current_day_index = ((new_day_idx - 1) % 7) + 1
                user.week_spent = 0.0
                user.week_spontaneous_spent = 0.0
                user.week_start_date = today_str
                # Сброс дневного лимита к базовому на начало новой недели
                user.current_daily_limit = user.base_daily_limit
            else:
                user.current_day_index = new_day_idx

            self.save_user(user)


storage = Storage()
