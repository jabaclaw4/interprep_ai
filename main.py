# main.py
import os
import sys
import asyncio
import logging
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# =========================
# Настройка логирования
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =========================
# Загрузка окружения
# =========================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN не найден в .env")

# =========================
# Глобальные переменные
# =========================
USE_RAG = False  # Определяем ДО использования
agents = {}

# Создаем папки при запуске (важно для Railway)
Path("data").mkdir(exist_ok=True)
Path("knowledge").mkdir(exist_ok=True)
Path("chroma_db").mkdir(exist_ok=True)

print(f"📁 Current directory: {os.getcwd()}")
print(f"📁 Contents: {os.listdir('.')}")

# Добавляем путь для импорта модулей
sys.path.append(str(Path(__file__).resolve().parent))

# =========================
# Импорты из нашего проекта
# =========================
# Сначала импортируем утилиты
from bot.utils import setup_rag, setup_database, get_bot_commands
from bot.config import WELCOME_MESSAGE

# Затем импортируем агентов (исправленные названия)
try:
    from agents.coordinator import CoordinatorAgent
    from agents.assessor_agent import AssessorAgent
    from agents.planner_agent import PlannerAgent
    from agents.interviewer_agent import InterviewerAgent
    from agents.reviewer import ReviewerAgent

    AGENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️  Некоторые агенты не найдены: {e}")
    AGENTS_AVAILABLE = False

# Импортируем middleware (исправленный импорт)
try:
    from bot.middleware.agents_middleware import AgentsMiddleware

    MIDDLEWARE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️  Middleware не найден: {e}")
    MIDDLEWARE_AVAILABLE = False

from bot.handlers.start import router as start_router
from bot.handlers.assessment import router as assessment_router
from bot.handlers.planning import router as planning_router  # если есть
from bot.handlers.interview import router as interview_router
from bot.handlers.review import router as review_router
from bot.handlers.general import router as general_router
# ДОБАВИТЬ импорт главного роутера:
from bot.handlers import main_router

# =========================
# Инициализация бота (aiogram 3.x)
# =========================
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
dp.include_router(main_router)

# Создаем словарь агентов - будет заполнен позже
agents_dict = {
    "coordinator": None,
    "assessor": None,
    "interviewer": None,
    "planner": None,
    "reviewer": None
}


# =========================
# Базовые обработчики команд (fallback на случай проблем)
# =========================
@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    """Начало работы с ботом"""
    try:
        status = "✅ Активна" if USE_RAG else "❌ Не активна"
        welcome_text = WELCOME_MESSAGE.format(status)
        await message.answer(welcome_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer(
            "🤖 <b>InterPrep AI v1.0</b>\n\n"
            "Интеллектуальный помощник для подготовки к IT-собеседованиям.\n\n"
            "Доступные команды:\n"
            "/start - Начало работы\n"
            "/begin [уровень] [направление] - Начать подготовку\n"
            "/assess - Оценка навыков\n"
            "/interview - Собеседование\n"
            "/plan - План обучения\n"
            "/review - Проверка кода\n"
            "/status - Статус системы",
            parse_mode=ParseMode.HTML
        )


@dp.message(Command("rag_status"))
async def cmd_rag_status(message: types.Message):
    """Проверка статуса RAG"""
    global USE_RAG
    if USE_RAG:
        try:
            from rag.retriever import check_database_status
            status = check_database_status()
            await message.answer(
                f"📊 <b>Статус RAG базы:</b>\n\n"
                f"✅ <b>Статус:</b> {status.get('status', 'unknown')}\n"
                f"📁 <b>Документов:</b> {status.get('documents_count', 0)}\n"
                f"📚 <b>Коллекция:</b> {status.get('collection_name', 'unknown')}"
            )
        except Exception as e:
            await message.answer(f"❌ Ошибка получения статуса RAG: {e}")
    else:
        await message.answer("⚠️ RAG модуль отключен")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Статус бота"""
    global agents_dict, USE_RAG

    # Проверяем какие агенты доступны
    active_agents = []
    for name, agent in agents_dict.items():
        if agent is not None:
            active_agents.append(name)

    agents_status = f"✅ {len(active_agents)}/{len(agents_dict)}" if active_agents else "❌ Нет"
    rag_status = "✅ ВКЛ" if USE_RAG else "❌ ВЫКЛ"

    await message.answer(
        f"🤖 <b>Статус InterPrep AI:</b>\n\n"
        f"🔄 <b>Бот:</b> Активен\n"
        f"🧠 <b>Агенты:</b> {agents_status}\n"
        f"📚 <b>RAG:</b> {rag_status}\n"
        f"💾 <b>База данных:</b> ✅ Готова\n\n"
        f"<b>Доступные агенты:</b>\n" + "\n".join([f"• {agent}" for agent in active_agents])
    )


# =========================
# Основная функция запуска
# =========================
async def main():
    """Главная функция запуска бота"""
    global USE_RAG, agents_dict

    logger.info("🚀 Запуск InterPrep AI...")

    # 1. Настройка базы данных
    try:
        if setup_database():
            logger.info("✅ База данных готова")
        else:
            logger.warning("⚠️  База данных не настроена")
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")

    # 2. Настройка RAG
    try:
        rag_status = setup_rag()
        USE_RAG = rag_status.get("status") == "ready"
        if USE_RAG:
            logger.info(f"✅ RAG база готова: {rag_status.get('documents_count', 0)} документов")
        else:
            logger.warning(f"⚠️  RAG база не готова: {rag_status.get('status', 'unknown')}")
    except Exception as e:
        logger.error(f"❌ Ошибка RAG: {e}")
        USE_RAG = False

    # 3. Инициализация агентов
    if AGENTS_AVAILABLE:
        try:
            coordinator = CoordinatorAgent(use_rag=USE_RAG)
            agents_dict = {
                "coordinator": coordinator,
                "assessor": AssessorAgent(use_rag=USE_RAG),
                "interviewer": InterviewerAgent(use_rag=USE_RAG),
                "planner": PlannerAgent(use_rag=USE_RAG),
                "reviewer": ReviewerAgent(use_rag=USE_RAG)
            }
            logger.info("✅ Агенты инициализированы")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации агентов: {e}")
            # Создаем базовые заглушки
            agents_dict = {}
    else:
        logger.warning("⚠️  Агенты не доступны, работаем в ограниченном режиме")
        agents_dict = {}

    # 4. Добавляем middleware для передачи агентов
    if MIDDLEWARE_AVAILABLE and agents_dict.get("coordinator"):
        try:
            agents_middleware = AgentsMiddleware(
                agents=agents_dict,
                use_rag=USE_RAG
            )
            dp.update.outer_middleware(agents_middleware)
            logger.info("✅ Middleware добавлен")
        except Exception as e:
            logger.error(f"❌ Ошибка middleware: {e}")
    else:
        logger.warning("⚠️  Middleware не добавлен")

    # 5. Регистрация хэндлеров через роутеры
    try:
        # Импортируем хэндлеры внутри функции
        from bot.handlers.start import router as start_router
        from bot.handlers.assessment import router as assessment_router
        from bot.handlers.planning import router as planning_router
        from bot.handlers.interview import router as interview_router
        from bot.handlers.review import router as review_router
        from bot.handlers.general import router as general_router

        print("✅ Все роутеры импортированы")

        # Регистрируем все роутеры
        dp.include_router(start_router)
        dp.include_router(assessment_router)
        dp.include_router(planning_router)
        dp.include_router(interview_router)
        dp.include_router(review_router)
        dp.include_router(general_router)

        print("✅ Все роутеры зарегистрированы в диспетчере")
        logger.info("✅ Хэндлеры зарегистрированы")
        HANDLERS_AVAILABLE = True

    except ImportError as e:
        print(f"❌ Ошибка импорта роутеров: {e}")
        logger.warning("⚠️  Хэндлеры не зарегистрированы, используем только базовые команды")
        HANDLERS_AVAILABLE = False
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации хэндлеров: {e}")
        print(f"❌ Ошибка при регистрации роутеров: {e}")
        HANDLERS_AVAILABLE = False

    # 6. Устанавливаем команды бота
    try:
        await bot.set_my_commands(get_bot_commands())
        logger.info("✅ Команды бота установлены")
    except Exception as e:
        logger.error(f"❌ Ошибка установки команд: {e}")

    logger.info("✅ InterPrep AI готов к работе!")
    print("\n" + "=" * 50)
    print("🤖 InterPrep AI запущен!")
    print("📚 RAG: " + ("✅ Активен" if USE_RAG else "❌ Отключен"))
    print(f"🧠 Агентов: {len([a for a in agents_dict.values() if a])}/{len(agents_dict)}")
    print("=" * 50 + "\n")

    # 7. Запуск поллинга
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка поллинга: {e}")
        raise


async def on_shutdown():
    """Завершение работы бота"""
    logger.info("👋 Завершение работы InterPrep AI...")
    try:
        await bot.close()
    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии бота: {e}")


# =========================
# Запуск бота
# =========================
if __name__ == "__main__":
    print("🤖 InterPrep AI v1.0 с RAG и SQLite")
    print("-" * 40)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Выключение по запросу пользователя...")
        asyncio.run(on_shutdown())
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        asyncio.run(on_shutdown())