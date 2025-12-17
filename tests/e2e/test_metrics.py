# tests/e2e/test_metrics.py
import pytest
import json
from pathlib import Path
from agents.coordinator import CoordinatorAgent
from agents.interviewer_agent import InterviewerAgent
from agents.assessor_agent import AssessorAgent
from agents.planner_agent import PlannerAgent


class TestAccuracyMetrics:
    """Тесты для метрики точности (>85%)."""

    @pytest.fixture(autouse=True)
    def load_test_scenarios(self, test_data_dir):
        """Загружаем тестовые сценарии."""
        scenarios_path = test_data_dir / "test_scenarios.json"
        with open(scenarios_path, 'r', encoding='utf-8') as f:
            self.scenarios = json.load(f)
        return self.scenarios

    async def test_overall_accuracy(self, coordinator_agent, interviewer_agent,
                                    assessor_agent, planner_agent):
        """Тест общей точности агентов."""
        results = {
            "coordinator": {"total": 0, "relevant": 0},
            "interviewer": {"total": 0, "relevant": 0},
            "assessor": {"total": 0, "relevant": 0},
            "planner": {"total": 0, "relevant": 0}
        }

        for scenario in self.scenarios[:15]:  # 15 сценариев как в отчете
            # Coordinator
            if "coordinator" in scenario["expected_agents"]:
                response = await coordinator_agent.process_query(scenario["user_query"])
                is_relevant = self._check_relevance(
                    response, scenario["required_keywords"]
                )
                results["coordinator"]["total"] += 1
                results["coordinator"]["relevant"] += int(is_relevant)

            # Interviewer
            if "interviewer" in scenario["expected_agents"]:
                questions = await interviewer_agent.generate_questions(
                    topic=scenario["topic"]
                )
                is_relevant = any(
                    self._check_relevance(q, scenario["required_keywords"])
                    for q in questions[:2]  # Проверяем первые 2 вопроса
                )
                results["interviewer"]["total"] += 1
                results["interviewer"]["relevant"] += int(is_relevant)

            # Assessor (симулируем ответ пользователя)
            if "assessor" in scenario["expected_agents"]:
                sample_answer = "Пример ответа пользователя"
                feedback = await assessor_agent.assess_answer(
                    question=scenario.get("sample_question", ""),
                    answer=sample_answer
                )
                is_relevant = self._check_relevance(
                    feedback, ["рекомендация", "совет", "улучшить"]
                )
                results["assessor"]["total"] += 1
                results["assessor"]["relevant"] += int(is_relevant)

            # Planner
            if "planner" in scenario.get("expected_agents", []):
                plan = await planner_agent.create_plan(
                    topics=[scenario["topic"]],
                    days=7
                )
                is_relevant = self._check_relevance(
                    plan, ["план", "день", "изучить"]
                )
                results["planner"]["total"] += 1
                results["planner"]["relevant"] += int(is_relevant)

        # Расчет метрик
        accuracy_metrics = {}
        for agent, data in results.items():
            if data["total"] > 0:
                accuracy = data["relevant"] / data["total"]
                accuracy_metrics[agent] = accuracy * 100

        # Общая точность (взвешенная)
        total_responses = sum(d["total"] for d in results.values())
        total_relevant = sum(d["relevant"] for d in results.values())
        overall_accuracy = (total_relevant / total_responses) * 100

        print(f"\n{'=' * 50}")
        print("РЕЗУЛЬТАТЫ ТОЧНОСТИ:")
        print(f"{'=' * 50}")
        for agent, accuracy in accuracy_metrics.items():
            print(f"{agent.capitalize():15} {accuracy:6.1f}%")
        print(f"{'=' * 50}")
        print(f"ОБЩАЯ ТОЧНОСТЬ:    {overall_accuracy:6.1f}%")
        print(f"{'=' * 50}")

        # Проверка порога
        assert overall_accuracy >= 85.0, f"Точность ниже 85%: {overall_accuracy:.1f}%"

        # Сохраняем метрики для отчета
        pytest.custom_metrics = {
            "accuracy_overall": overall_accuracy,
            "accuracy_by_agent": accuracy_metrics,
            "total_scenarios": len(self.scenarios)
        }

    def _check_relevance(self, text, required_keywords):
        """Проверка релевантности по ключевым словам."""
        if not text:
            return False

        text_lower = text.lower()
        # Проверяем наличие ключевых слов
        keyword_match = any(
            keyword.lower() in text_lower
            for keyword in required_keywords
        ) if required_keywords else True

        # Дополнительные эвристики
        is_complete = len(text.strip()) > 10
        has_structure = any(marker in text for marker in ['. ', '! ', '? ', '\n'])

        return keyword_match and is_complete and has_structure