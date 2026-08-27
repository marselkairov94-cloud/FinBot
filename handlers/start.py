from aiogram import Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.storage import storage
from database.models import UserProfile
from keyboards.reply import get_main_menu_keyboard
from keyboards.inline import get_skip_pet_name_keyboard
from config import CURRENCY_SYMBOL

router = Router()


class SetPetNameState(StatesGroup):
    waiting_for_name = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start: сброс состояния и обязательный запрос имени питомца."""
    await state.clear()
    user_id = message.from_user.id
    existing_user = storage.get_user(user_id)

    nick = message.from_user.username
    if not nick:
        nick = message.from_user.first_name or str(user_id)

    user = existing_user or UserProfile(user_id=user_id, nickname=nick, pet_name="Тамагочи")
    storage.save_user(user)

    await state.set_state(SetPetNameState.waiting_for_name)
    await message.answer(
        f"Добро пожаловать в FinBot, {nick}.\n\n"
        f"Это цифровой помощник по планированию расходов с игровым элементом Тамагочи.\n"
        f"Вместе с вами за бюджетом будет следить ваш виртуальный питомец.\n"
        f"Запланированные траты дают питомцу опыт (+10 EXP), а спонтанные отнимают здоровье (-15 HP).\n"
        f"Превышение дневного лимита также отнимает здоровье (-10 HP).\n\n"
        f"Как вы хотите назвать своего питомца?\n"
        f"Напишите имя в чат или нажмите кнопку «Пропустить».",
        reply_markup=get_skip_pet_name_keyboard()
    )


@router.callback_query(SetPetNameState.waiting_for_name, F.data == "skip_pet_name")
@router.callback_query(F.data == "skip_pet_name")
async def process_skip_pet_name(callback: CallbackQuery, state: FSMContext):
    """Пропуск выбора имени питомца (по умолчанию: Тамагочи)."""
    user_id = callback.from_user.id
    user = storage.get_user(user_id) or UserProfile(user_id=user_id, nickname=str(user_id))
    user.pet_name = "Тамагочи"
    storage.save_user(user)
    await state.clear()

    await callback.message.edit_text(
        f"Отлично! Вашего питомца зовут {user.pet_name}.\n\n"
        f"Запланированные траты дают питомцу опыт (+10 EXP), спонтанные отнимают здоровье (-15 HP), "
        f"а перерасход дневного лимита отнимает -10 HP.\n\n"
        f"Выберите сценарий работы в меню ниже:\n\n"
        f"1. Накопить на цель: расчет безопасного дневного лимита и накопление на мечту.\n"
        f"2. Контролировать лимит: прямой контроль бюджета без конкретной цели."
    )
    await callback.message.answer("Главное меню доступно:", reply_markup=get_main_menu_keyboard())
    await callback.answer()


@router.message(SetPetNameState.waiting_for_name)
async def process_custom_pet_name(message: Message, state: FSMContext):
    """Сохранение введенного имени питомца (не обрабатывается как расход!)."""
    pet_name = message.text.strip()
    if len(pet_name) < 1 or len(pet_name) > 30:
        await message.answer("Пожалуйста, введите имя питомца от 1 до 30 символов:")
        return

    user_id = message.from_user.id
    user = storage.get_user(user_id) or UserProfile(user_id=user_id, nickname=message.from_user.username or str(user_id))
    user.pet_name = pet_name
    storage.save_user(user)
    await state.clear()

    await message.answer(
        f"Отлично! Вашего питомца зовут {pet_name}.\n\n"
        f"Запланированные траты дают питомцу опыт (+10 EXP), спонтанные отнимают здоровье (-15 HP), "
        f"а перерасход дневного лимита отнимает -10 HP.\n\n"
        f"Выберите сценарий работы в меню ниже:\n\n"
        f"1. Накопить на цель: расчет безопасного дневного лимита и накопление на мечту.\n"
        f"2. Контролировать лимит: прямой контроль бюджета без конкретной цели.",
        reply_markup=get_main_menu_keyboard()
    )
