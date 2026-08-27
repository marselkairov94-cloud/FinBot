from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    keyboard = [
        [
            KeyboardButton(text="Накопить на цель"),
            KeyboardButton(text="Контролировать лимит")
        ],
        [
            KeyboardButton(text="Питомец"),
            KeyboardButton(text="Текущий статус")
        ],
        [
            KeyboardButton(text="Сбросить настройки")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
        input_field_placeholder="Введите сумму или фразу расхода"
    )
