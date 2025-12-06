# bot/middleware/agents_middleware.py
from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
import logging
from agents.coordinator import CoordinatorAgent

logger = logging.getLogger(__name__)

# Глобальный экземпляр координатора
_coordinator = None


class AgentsMiddleware(BaseMiddleware):
    """Middleware для передачи агентов в хэндлеры"""

    def __init__(self, agents: Dict[str, Any], use_rag: bool = False):
        super().__init__()
        self.agents = agents
        self.use_rag = use_rag

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        # Передаем агенты в data для использования в хэндлерах
        data['agents'] = self.agents
        data['use_rag'] = self.use_rag

        # Также добавляем координатор для быстрого доступа
        data['coordinator'] = get_coordinator()

        return await handler(event, data)


def get_coordinator() -> CoordinatorAgent:
    """Возвращает экземпляр координатора (синглтон)"""
    global _coordinator
    if _coordinator is None:
        _coordinator = CoordinatorAgent(use_rag=False)
        logger.info("✅ Координатор инициализирован")
    return _coordinator


def set_coordinator(coordinator: CoordinatorAgent):
    """Устанавливает координатора (для тестов)"""
    global _coordinator
    _coordinator = coordinator