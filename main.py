import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from handlers import (
    common_router,
    goal_router,
    limit_router,
    expenses_router
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FinBot")


async def set_bot_commands(bot: Bot) -> None:
    """Установка списка команд в меню Telegram."""
    commands = [
        BotCommand(command="start", description="Начать работу и регистрация"),
        BotCommand(command="pet", description="Мой виртуальный питомец"),
        BotCommand(command="stats", description="Статистика трат"),
        BotCommand(command="status", description="Текущий баланс и лимиты"),
        BotCommand(command="help", description="Справка по использованию"),
        BotCommand(command="reset", description="Сбросить профиль и настройки"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    """Главная функция запуска бота."""
    logger.info("Запуск FinBot...")

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.warning(
            "Внимание: Токен бота не задан в .env файле. "
            "Укажите BOT_TOKEN в файле .env (создайте его на основе .env.example)."
        )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок регистрации роутеров:
    dp.include_router(common_router)
    dp.include_router(goal_router)
    dp.include_router(limit_router)
    dp.include_router(expenses_router)

    try:
        await set_bot_commands(bot)
    except Exception as e:
        logger.warning(f"Не удалось установить команды меню: {e}")

    logger.info("FinBot запущен и готов к работе.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("FinBot остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот завершил работу.")
