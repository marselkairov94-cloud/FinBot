import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()]

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

EXPENSES_CSV = DATA_DIR / "expenses_dataset.csv"

MIN_REALISTIC_DAILY_LIMIT = 100.0
CURRENCY_SYMBOL = "₸"

EXPENSE_CATEGORIES = [
    "Еда и фастфуд",
    "Транспорт",
    "Маркетплейсы",
    "Игры и подписки",
    "Другое",
]
