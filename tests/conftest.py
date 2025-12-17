# tests/conftest.py
import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Импорты из вашего проекта
from agents.assessor_agent import AssessorAgent
from agents.coordinator import CoordinatorAgent
from agents.interviewer_agent import InterviewerAgent
from agents.planner_agent import PlannerAgent
from agents.reviewer import ReviewerAgent
from rag.retriever import (
    retrieve_context,
    retrieve_for_agent,
    get_questions_by_topic,
    build_prompt_with_context,
    check_database_status
)


@pytest.fixture
def test_data_dir():
    """Путь к тестовым данным."""
    return project_root / "tests" / "fixtures"


@pytest.fixture
def mock_vectorstore():
    """Мок векторного хранилища ChromaDB."""
    mock_vs = Mock()

    # Мокаем методы, которые использует ваш RAG
    mock_vs.query = Mock(return_value={
        'documents': [['Пример документа 1', 'Пример документа 2']],
        'metadatas': [[
            {'type': 'interview_question', 'topic': 'Python', 'difficulty': 'easy'},
            {'type': 'code_example', 'topic': 'Python', 'agent': 'reviewer'}
        ]]
    })

    mock_vs.count = Mock(return_value=100)
    mock_vs.get = Mock(return_value={
        'metadatas': [
            {'type': 'interview_question', 'agent': 'interviewer'},
            {'type': 'code_example', 'agent': 'reviewer'},
            {'type': 'learning_plan', 'agent': 'planner'}
        ]
    })

    return mock_vs


@pytest.fixture(autouse=True)
def mock_rag_dependencies(mock_vectorstore):
    """Мокаем зависимости RAG системы для тестов."""

    # 1. Мокаем get_vectorstore чтобы возвращать наш mock
    with patch('rag.retriever.get_vectorstore', return_value=mock_vectorstore):
        # 2. Мокаем проверку директории
        with patch('pathlib.Path.exists', return_value=True):
            # 3. Мокаем client
            mock_client = Mock()
            mock_client.get_collection = Mock(return_value=mock_vectorstore)

            with patch('chromadb.PersistentClient', return_value=mock_client):
                yield


@pytest.fixture
def sample_questions():
    """Пример вопросов для тестов."""
    return [
        {
            "question": "Что такое инкапсуляция в ООП?",
            "answer": "Инкапсуляция - это механизм языка, позволяющий объединить данные и методы, работающие с ними, в единый объект.",
            "topic": "Python",
            "difficulty": "easy",
            "level": "junior"
        },
        {
            "question": "Чем отличается list от tuple в Python?",
            "answer": "List изменяемый, tuple неизменяемый. List использует квадратные скобки [], tuple - круглые ().",
            "topic": "Python",
            "difficulty": "easy",
            "level": "junior"
        }
    ]


@pytest.fixture
async def assessor_agent():
    """Фикстура для агента1-оценщика с моком RAG."""
    agent = AssessorAgent()

    # Мокаем LLM
    agent.llm = Mock()
    agent.llm.invoke = AsyncMock(return_value=Mock(
        content="""Хороший ответ! Вы правильно объяснили концепцию. 
        Рекомендую также изучить: 
        1. Примеры использования в реальных проектах
        2. Как это реализовано в стандартной библиотеке Python
        3. Паттерны проектирования, использующие эту концепцию"""
    ))

    # Мокаем RAG зависимость если она есть
    if hasattr(agent, 'rag_retriever'):
        agent.rag_retriever = Mock()
        agent.rag_retriever.retrieve_context = AsyncMock(
            return_value=["Пример контекста для оценки"]
        )

    return agent


@pytest.fixture
async def interviewer_agent(sample_questions):
    """Фикстура для интервьюера с моком RAG."""
    agent = InterviewerAgent()

    # Мокаем LLM
    agent.llm = Mock()
    agent.llm.invoke = AsyncMock(return_value=Mock(
        content="Вопрос: Объясните принцип полиморфизма с примером на Python"
    ))

    # Мокаем RAG (ваш текущий интерфейс)
    agent.get_questions_from_knowledge_base = Mock(return_value=sample_questions)

    # Если используется прямое обращение к retriever
    if hasattr(agent, 'retriever'):
        agent.retriever = Mock()
        agent.retriever.get_questions_by_topic = Mock(return_value=sample_questions)

    return agent


@pytest.fixture
async def coordinator_agent():
    """Фикстура для координатора."""
    agent = CoordinatorAgent()
    agent.llm = Mock()
    agent.llm.invoke = AsyncMock(return_value=Mock(
        content="INTERVIEWER:python:ООП"
    ))
    return agent


@pytest.fixture
async def planner_agent():
    """Фикстура для планировщика."""
    agent = PlannerAgent()
    agent.llm = Mock()
    agent.llm.invoke = AsyncMock(return_value=Mock(
        content="""План обучения на 7 дней:
        День 1: Основы Python
        День 2: ООП в Python
        День 3: Структуры данных
        День 4: Алгоритмы
        День 5: Базы данных
        День 6: Веб-фреймворки
        День 7: Практика и повторение"""
    ))
    return agent


@pytest.fixture
def rag_retriever():
    """Фикстура для тестирования RAG модуля напрямую."""
    # Здесь мы будем тестировать реальный модуль, но с моками
    return sys.modules['rag.retriever']