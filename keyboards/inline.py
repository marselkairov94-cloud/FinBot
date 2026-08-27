from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import EXPENSE_CATEGORIES


def get_categories_keyboard(expense_amount: float) -> InlineKeyboardMarkup:
    """Выбор категории расходов."""
    buttons = []
    row = []
    for idx, category in enumerate(EXPENSE_CATEGORIES):
        row.append(InlineKeyboardButton(
            text=category,
            callback_data=f"cat:{idx}:{expense_amount}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_impulsiveness_keyboard(category_idx: int, expense_amount: float) -> InlineKeyboardMarkup:
    """Выбор типа траты (Планировал / Спонтанно)."""
    buttons = [
        [
            InlineKeyboardButton(
                text="Планировал",
                callback_data=f"imp:planned:{category_idx}:{expense_amount}"
            ),
            InlineKeyboardButton(
                text="Спонтанно",
                callback_data=f"imp:spontaneous:{category_idx}:{expense_amount}"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reality_fix_keyboard(realistic_weeks: int) -> InlineKeyboardMarkup:
    """Кнопки для корректировки нереалистичного срока накопления."""
    months = round(realistic_weeks / 4.0, 1)
    buttons = [
        [
            InlineKeyboardButton(
                text=f"Установить срок {realistic_weeks} нед. (~{months} мес.)",
                callback_data=f"fix_goal_weeks:{realistic_weeks}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Ввести другой срок",
                callback_data="fix_goal_weeks:custom"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_limit_type_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора формата лимита."""
    buttons = [
        [
            InlineKeyboardButton(
                text="Дневной лимит",
                callback_data="limit_type:daily"
            ),
            InlineKeyboardButton(
                text="Недельный бюджет",
                callback_data="limit_type:weekly"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_skip_pet_name_keyboard() -> InlineKeyboardMarkup:
    """Кнопка для пропуска выбора имени питомца."""
    buttons = [
        [
            InlineKeyboardButton(
                text="Пропустить (Тамагочи)",
                callback_data="skip_pet_name"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
