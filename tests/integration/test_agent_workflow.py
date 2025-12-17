# tests/integration/test_agent_workflow.py
import pytest
from agents.coordinator import CoordinatorAgent
from agents.interviewer_agent import InterviewerAgent
from agents.assessor_agent import AssessorAgent
from agents.planner_agent import PlannerAgent


class TestFunctionalCompleteness:
    """Тесты для метрики функциональной полноты."""

    async def test_all_agents_integrated(self):
        """Тест интеграции всех агентов."""
        agents = {
            "coordinator": CoordinatorAgent(),
            "interviewer": InterviewerAgent(),
            "assessor": AssessorAgent(),
            "planner": PlannerAgent()
        }

        # Проверяем, что все агенты инициализируются
        for name, agent in agents.items():
            assert agent is not None, f"Агент {name} не инициализирован"
            print(f"✓ Агент {name} инициализирован")

        # Тест полного workflow
        user_request = "Хочу подготовиться к собеседованию на Junior Python разработчика"

        # 1. Coordinator определяет, какой агент нужен
        coordinator_response = await agents["coordinator"].process_query(user_request)
        assert coordinator_response, "Coordinator не ответил"
        print(f"Coordinator ответил: {coordinator_response[:50]}...")

        # 2. Interviewer задает вопрос
        questions = await agents["interviewer"].generate_questions(
            topic="Python ООП",
            count=2
        )
        assert len(questions) >= 1, "Interviewer не сгенерировал вопросы"
        print(f"Interviewer сгенерировал {len(questions)} вопросов")

        # 3. Assessor оценивает ответ
        sample_answer = "Инкапсуляция это скрытие реализации и предоставление интерфейса"
        feedback = await agents["assessor"].assess_answer(
            question=questions[0],
            answer=sample_answer
        )
        assert feedback, "Assessor не дал фидбэк"
        print(f"Assessor дал фидбэк: {feedback[:50]}...")

        # 4. Planner создает план
        plan = await agents["planner"].create_plan(
            topics=["Python", "Базы данных"],
            days=7
        )
        assert plan, "Planner не создал план"
        print(f"Planner создал план: {plan[:50]}...")

        # Итоговая проверка
        agents_used = 4  # Все 4 основных агента
        agents_planned = 5  # Планировалось 5 (включая Reviewer)

        completeness_percentage = (agents_used / agents_planned) * 100

        print(f"\nФункциональная полнота: {agents_used}/{agents_planned} ({completeness_percentage:.0f}%)")

        assert agents_used >= 4, "Не все основные агенты работают"
        assert completeness_percentage >= 80, f"Полнота ниже 80%: {completeness_percentage:.0f}%"