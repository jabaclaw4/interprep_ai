# bot/utils.py
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Глобальные хранилища для контекста и состояний пользователей
_user_contexts: Dict[str, Dict[str, Any]] = {}
_user_states: Dict[str, Dict[str, Any]] = {}


def setup_database() -> bool:
    """Инициализация базы данных"""
    try:
        from db.models import init_db
        engine = init_db()

        # Проверяем подключение
        from db.models import SessionLocal
        with SessionLocal() as db:
            from db.models import User
            user_count = db.query(User).count()
            logger.info(f"👥 Пользователей в БД: {user_count}")

        return True
    except Exception as e:
        logger.error(f"❌ Ошибка БД: {e}")
        return False


def setup_rag() -> Dict[str, Any]:
    """Проверка и настройка RAG"""
    try:
        from rag.retriever import check_database_status
        status = check_database_status()
        return status
    except ImportError:
        logger.warning("RAG модуль не найден")
        return {"status": "not_found", "error": "Module not found"}
    except Exception as e:
        logger.error(f"Ошибка RAG: {e}")
        return {"status": "error", "error": str(e)}


def setup_agents(use_rag: bool = False) -> Dict[str, Any]:
    """Инициализация всех агентов"""
    agents = {}

    try:
        # Пробуем импортировать всех агентов
        try:
            from agents.coordinator import CoordinatorAgent
            from agents.assessor import AssessorAgent
            from agents.planner import PlannerAgent
            from agents.interviewer import InterviewerAgent
            from agents.reviewer import ReviewerAgent

            agents["coordinator"] = CoordinatorAgent(use_rag=use_rag)
            agents["assessor"] = AssessorAgent(use_rag=use_rag)
            agents["planner"] = PlannerAgent(use_rag=use_rag)
            agents["interviewer"] = InterviewerAgent(use_rag=use_rag)
            agents["reviewer"] = ReviewerAgent(use_rag=use_rag)

            # Проверяем, создались ли агенты
            for name, agent in agents.items():
                if not agent:
                    logger.warning(f"⚠️  Агент {name} не создан")
                    agents[name] = None

            logger.info(f"✅ Агенты созданы (RAG: {'ВКЛ' if use_rag else 'ВЫКЛ'})")

        except ImportError as import_error:
            logger.warning(f"⚠️  Не все агенты доступны: {import_error}")

            # Создаем заглушки для отсутствующих агентов
            class StubAgent:
                def __init__(self, name):
                    self.name = name

                def route(self, *args, **kwargs):
                    return type('obj', (object,), {
                        'agent': 'ASSESSOR',
                        'context': 'Недоступно',
                        'metadata': {}
                    })()

                def assess(self, *args, **kwargs):
                    return type('obj', (object,), {
                        'scores': {},
                        'follow_up': 'Агент временно недоступен',
                        'context_used': False
                    })()

            if "coordinator" not in agents:
                agents["coordinator"] = StubAgent("coordinator")
            if "assessor" not in agents:
                agents["assessor"] = StubAgent("assessor")
            if "planner" not in agents:
                agents["planner"] = StubAgent("planner")
            if "interviewer" not in agents:
                agents["interviewer"] = StubAgent("interviewer")
            if "reviewer" not in agents:
                agents["reviewer"] = StubAgent("reviewer")

        return agents

    except Exception as e:
        logger.error(f"❌ Ошибка создания агентов: {e}")
        # Возвращаем пустой словарь, чтобы бот мог работать в базовом режиме
        return {}

def get_or_create_user(message, db: Session = None) -> Tuple[Any, Session]:
    """Получает или создает пользователя"""
    from db.models import SessionLocal
    from db.repository import UserRepository

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        user = UserRepository.get_or_create_user(
            db=db,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

        logger.info(f"👤 Пользователь получен/создан: {user.username or user.telegram_id}")
        return user, db

    except Exception as e:
        logger.error(f"❌ Ошибка работы с пользователем: {e}")
        if close_db:
            db.rollback()
        raise
    finally:
        if close_db:
            db.close()


def get_bot_commands() -> list:
    """Возвращает список команд для бота"""
    from aiogram import types

    return [
        types.BotCommand(command="start", description="Запуск бота"),
        types.BotCommand(command="help", description="Помощь"),
        types.BotCommand(command="begin", description="Начать подготовку"),
        types.BotCommand(command="assess", description="Оценка навыков"),
        types.BotCommand(command="interview", description="Собеседование"),
        types.BotCommand(command="plan", description="План обучения"),
        types.BotCommand(command="review", description="Проверка кода"),
        types.BotCommand(command="progress", description="Мой прогресс"),
        types.BotCommand(command="status", description="Статус системы"),
        types.BotCommand(command="rag_status", description="Статус RAG"),
    ]


# ============================================
# Функции для работы с контекстом пользователя
# ============================================

def get_user_context(user_id: str) -> Dict[str, Any]:
    """Получает контекст пользователя"""
    return _user_contexts.get(user_id, {})


def set_user_context(user_id: str, context: Dict[str, Any]):
    """Устанавливает контекст пользователя"""
    _user_contexts[user_id] = context
    logger.debug(f"✅ Контекст установлен для {user_id}: {context}")


def ensure_user_context(user_id: str) -> Dict[str, Any]:
    """Гарантирует, что у пользователя есть контекст"""
    context = get_user_context(user_id)
    if not context:
        # Создаем контекст по умолчанию
        context = {
            'level': 'junior',
            'track': 'backend',
            'current_mode': None,
            'created_at': get_current_timestamp()
        }
        set_user_context(user_id, context)
    return context


def update_user_context(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Обновляет контекст пользователя"""
    context = ensure_user_context(user_id)
    context.update(updates)
    set_user_context(user_id, context)
    return context


def update_user_level(user_id: str, level: str):
    """Обновляет уровень пользователя"""
    update_user_context(user_id, {'level': level})
    logger.info(f"📊 Уровень пользователя {user_id} обновлен: {level}")


def update_user_track(user_id: str, track: str):
    """Обновляет направление пользователя"""
    update_user_context(user_id, {'track': track})
    logger.info(f"🎯 Направление пользователя {user_id} обновлено: {track}")


def update_user_mode(user_id: str, mode: Optional[str]):
    """Обновляет текущий режим пользователя"""
    update_user_context(user_id, {'current_mode': mode})
    if mode:
        logger.debug(f"🔄 Режим пользователя {user_id} изменен: {mode}")


def clear_user_context(user_id: str):
    """Очищает контекст пользователя"""
    if user_id in _user_contexts:
        del _user_contexts[user_id]
        logger.debug(f"🧹 Контекст пользователя {user_id} очищен")


# ============================================
# Функции для работы с состояниями пользователя
# ============================================

def set_user_state(user_id: str, state: Dict[str, Any]):
    """Устанавливает состояние пользователя"""
    _user_states[user_id] = state
    logger.debug(f"🔧 Состояние установлено для {user_id}: {state}")


def get_user_state(user_id: str) -> Dict[str, Any]:
    """Получает состояние пользователя"""
    return _user_states.get(user_id, {})


def clear_user_state(user_id: str):
    """Очищает состояние пользователя"""
    if user_id in _user_states:
        del _user_states[user_id]
        logger.debug(f"🧹 Состояние пользователя {user_id} очищено")


def update_user_state(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Обновляет состояние пользователя"""
    state = get_user_state(user_id)
    state.update(updates)
    set_user_state(user_id, state)
    return state


# ============================================
# Вспомогательные функции
# ============================================

def get_current_timestamp() -> str:
    """Возвращает текущую временную метку"""
    from datetime import datetime
    return datetime.now().isoformat()


def format_user_info(user_id: str) -> str:
    """Форматирует информацию о пользователе для логов"""
    context = get_user_context(user_id)
    state = get_user_state(user_id)

    info_parts = []

    if context:
        info_parts.append(f"level={context.get('level', '?')}")
        info_parts.append(f"track={context.get('track', '?')}")
        if context.get('current_mode'):
            info_parts.append(f"mode={context['current_mode']}")

    if state:
        if state.get('mode'):
            info_parts.append(f"state_mode={state['mode']}")

    if info_parts:
        return f"({', '.join(info_parts)})"
    return ""


def log_user_action(user_id: str, action: str, details: str = ""):
    """Логирует действие пользователя с контекстом"""
    user_info = format_user_info(user_id)
    log_message = f"👤 {user_id} {user_info}: {action}"
    if details:
        log_message += f" - {details}"
    logger.info(log_message)


# ============================================
# Функции для координатора
# ============================================

def prepare_user_context_for_coordinator(user_id: str) -> Dict[str, Any]:
    """Подготавливает контекст для передачи в координатор"""
    context = get_user_context(user_id)
    state = get_user_state(user_id)

    # Создаем контекст для координатора
    coordinator_context = context.copy()

    # Добавляем информацию о состоянии
    if state:
        coordinator_context['current_state'] = state.get('mode')
        coordinator_context['state_details'] = state

    return coordinator_context
