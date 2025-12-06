# agents/coordinator.py
import json
import sys
from pathlib import Path
from pydantic import BaseModel
from gigachat import GigaChat
from dotenv import load_dotenv
import os
from typing import Dict, Any, Optional

# Добавляем путь для импорта
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Импортируем RAG (с обработкой ошибок)
try:
    from rag.retriever import retrieve_context

    RAG_AVAILABLE = True
except ImportError:
    print("⚠️  RAG модуль не найден. Coordinator будет работать без базы знаний.")
    RAG_AVAILABLE = False


    def retrieve_context(query: str, k: int = 4) -> list:
        return []

load_dotenv()


class RouteResult(BaseModel):
    agent: str
    context: str
    metadata: dict
    confidence: float
    suggested_topics: Optional[list] = None
    rag_context_used: Optional[bool] = False


class CoordinatorAgent:
    def __init__(self, use_rag: bool = True):
        load_dotenv()
        self.client_secret = os.getenv("GIGACHAT_CLIENT_SECRET")
        if not self.client_secret:
            raise ValueError("❌ Не найден GIGACHAT_CLIENT_SECRET в .env")

        self.llm = GigaChat(
            credentials=self.client_secret,
            verify_ssl_certs=False,
            model="GigaChat"
        )
        self.use_rag = use_rag and RAG_AVAILABLE
        self.user_states = {}  # user_id -> state

    def route(self, user_text: str, user_context: dict = None, user_id: str = None) -> RouteResult:
        """Основной метод маршрутизации"""

        if user_context is None:
            user_context = {}

        state = self.user_states.get(user_id, {})
        current_mode = state.get('mode')

        print(f"🔍 Coordinator: '{user_text[:50]}...', mode={current_mode}, user_id={user_id}")

        # 1. Проверяем если это прямое описание навыков после /assess
        if current_mode == 'awaiting_assessment_details':
            # Очищаем состояние и отправляем к ASSESSOR
            if user_id in self.user_states:
                self.user_states[user_id]['mode'] = 'assessment_in_progress'
                self.user_states[user_id]['skills'] = user_text

            return RouteResult(
                agent="ASSESSOR",
                context=f"Пользователь описал навыки для оценки: {user_text[:100]}...",
                metadata={
                    "action": "process_skills",
                    "skills_text": user_text,
                    "source": "assessment_flow"
                },
                confidence=0.95,
                suggested_topics=["Python", "Django", "Backend"],
                rag_context_used=False
            )

        # 2. Проверяем если это описание навыков (даже без состояния)
        text_lower = user_text.lower()

        # Явные признаки описания навыков
        skill_indicators = [
            'знаю', 'опыт', 'работал', 'владею', 'умею',
            'python', 'django', 'java', 'javascript',
            'год', 'лет', 'месяц', 'проект'
        ]

        skill_count = sum(1 for indicator in skill_indicators if indicator in text_lower)
        has_comma = ',' in user_text
        word_count = len(user_text.split())

        # Если похоже на описание навыков
        if skill_count >= 2 and (has_comma or word_count >= 4):
            # Устанавливаем состояние
            if user_id:
                self.user_states[user_id] = {
                    'mode': 'assessment_in_progress',
                    'skills': user_text
                }

            return RouteResult(
                agent="ASSESSOR",
                context=f"Обнаружено описание навыков пользователя",
                metadata={
                    "action": "assess_skills",
                    "skill_indicators_found": skill_count,
                    "text_length": word_count
                },
                confidence=0.85,
                rag_context_used=False
            )

        # 3. Проверяем другие типы запросов
        # План обучения
        plan_keywords = ['хочу изучать', 'научиться', 'освоить', 'изуч', 'обуч', 'планир']
        if any(keyword in text_lower for keyword in plan_keywords):
            if user_id:
                self.user_states[user_id] = {'mode': 'planning'}

            return RouteResult(
                agent="PLANNER",
                context=f"Пользователь хочет создать план обучения",
                metadata={"intent": "learning_plan"},
                confidence=0.8,
                rag_context_used=False
            )

        # Собеседование
        interview_keywords = ['собеседован', 'интервью', 'вопросы', 'mock']
        if any(keyword in text_lower for keyword in interview_keywords):
            return RouteResult(
                agent="INTERVIEWER",
                context=f"Запрос на собеседование",
                metadata={"intent": "interview"},
                confidence=0.8,
                rag_context_used=False
            )

        # Code review
        code_keywords = ['код', 'решен', 'задач', 'алгоритм']
        if any(keyword in text_lower for keyword in code_keywords):
            return RouteResult(
                agent="REVIEWER",
                context=f"Запрос на разбор кода",
                metadata={"intent": "code_review"},
                confidence=0.8,
                rag_context_used=False
            )

        # 4. Если ничего не подошло - общий помощник
        return RouteResult(
            agent="HELPER",
            context="Не удалось определить конкретный запрос",
            metadata={"fallback": True, "text_analysis": "no_clear_intent"},
            confidence=0.3,
            rag_context_used=False
        )

    def set_user_state(self, user_id: str, mode: str, data: dict = None):
        """Устанавливает состояние пользователя"""
        if data is None:
            data = {}

        self.user_states[user_id] = {
            'mode': mode,
            **data
        }
        print(f"✅ Установлено состояние для {user_id}: {mode}")

    def clear_user_state(self, user_id: str):
        """Очищает состояние пользователя"""
        if user_id in self.user_states:
            del self.user_states[user_id]
            print(f"✅ Очищено состояние для {user_id}")