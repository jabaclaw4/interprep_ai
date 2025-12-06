# bot/middleware/states.py
from typing import Dict, Any

# Хранилище состояний пользователей
_user_states: Dict[str, Dict[str, Any]] = {}
_user_contexts: Dict[str, Dict[str, Any]] = {}

def set_user_state(user_id: str, state: Dict[str, Any]):
    """Устанавливает состояние пользователя"""
    _user_states[user_id] = state

def get_user_state(user_id: str) -> Dict[str, Any]:
    """Получает состояние пользователя"""
    return _user_states.get(user_id, {})

def clear_user_state(user_id: str):
    """Очищает состояние пользователя"""
    if user_id in _user_states:
        del _user_states[user_id]

def set_user_context(user_id: str, context: Dict[str, Any]):
    """Устанавливает контекст пользователя"""
    _user_contexts[user_id] = context

def get_user_context(user_id: str) -> Dict[str, Any]:
    """Получает контекст пользователя"""
    return _user_contexts.get(user_id, {})

def update_user_context(user_id: str, updates: Dict[str, Any]):
    """Обновляет контекст пользователя"""
    if user_id not in _user_contexts:
        _user_contexts[user_id] = {}
    _user_contexts[user_id].update(updates)