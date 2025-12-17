# tests/e2e/test_feedback_quality.py
import pytest
from agents.assessor_agent import AssessorAgent


class TestFeedbackQuality:
    """Тесты для метрики качества обратной связи (>80%)."""

    async def test_feedback_usefulness(self, assessor_agent, sample_feedback_cases):
        """Тест полезности рекомендаций."""
        useful_count = 0
        total_cases = len(sample_feedback_cases)

        for case in sample_feedback_cases:
            feedback = await assessor_agent.assess_answer(
                question=case["question"],
                answer=case["user_answer"]
            )

            # Критерии полезности
            usefulness_score = self._calculate_usefulness_score(
                feedback, case["expected_feedback_keywords"]
            )

            if usefulness_score >= 0.7:  # Порог полезности
                useful_count += 1

            print(f"\nВопрос: {case['question'][:50]}...")
            print(f"Ответ: {case['user_answer'][:50]}...")
            print(f"Фидбэк: {feedback[:100]}...")
            print(f"Score: {usefulness_score:.2f}")

        usefulness_percentage = (useful_count / total_cases) * 100

        assert usefulness_percentage >= 80.0, \
            f"Полезность фидбэка ниже 80%: {usefulness_percentage:.1f}%"

    def _calculate_usefulness_score(self, feedback, expected_keywords):
        """Расчет score полезности фидбэка."""
        score = 0

        # 1. Наличие ключевых слов
        feedback_lower = feedback.lower()
        keyword_match = sum(
            1 for keyword in expected_keywords
            if keyword.lower() in feedback_lower
        )
        score += (keyword_match / len(expected_keywords)) * 0.4

        # 2. Конкретность (длина и детализация)
        if len(feedback.split()) > 25:
            score += 0.3

        # 3. Наличие рекомендаций
        recommendation_indicators = [
            "советую", "рекомендую", "изучи", "посмотри",
            "попробуй", "практикуй"
        ]
        if any(indicator in feedback_lower for indicator in recommendation_indicators):
            score += 0.2

        # 4. Структурированность
        if any(marker in feedback for marker in ["1.", "- ", "* ", "• "]):
            score += 0.1

        return min(score, 1.0)  # Ограничиваем 1.0