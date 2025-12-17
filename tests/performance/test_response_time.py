# tests/performance/test_response_time.py
import pytest
import time
import asyncio
from agents.coordinator import CoordinatorAgent
from agents.interviewer_agent import InterviewerAgent


class TestPerformanceMetrics:
    """Тесты для метрики производительности."""

    @pytest.mark.performance
    async def test_response_time_threshold(self):
        """Тест времени ответа (<3 секунд)."""
        coordinator = CoordinatorAgent()
        interviewer = InterviewerAgent()

        test_queries = [
            ("Простой", "Привет, что ты умеешь?"),
            ("Технический", "Расскажи о принципах SOLID"),
            ("Сложный", "Как оптимизировать запрос с JOIN 5 таблиц?"),
            ("Планирование", "Создай план изучения Python на месяц")
        ]

        results = []

        for query_type, query in test_queries:
            # Тестируем Coordinator
            start_time = time.time()
            try:
                response = await coordinator.process_query(query)
                elapsed = time.time() - start_time
                results.append({
                    "agent": "coordinator",
                    "query_type": query_type,
                    "time": elapsed,
                    "success": True
                })

                print(f"Coordinator - {query_type}: {elapsed:.2f} сек")

                # Если запрос технический, тестируем Interviewer
                if query_type in ["Технический", "Сложный"]:
                    start_time = time.time()
                    questions = await interviewer.generate_questions(
                        topic="Python",
                        count=2
                    )
                    elapsed = time.time() - start_time
                    results.append({
                        "agent": "interviewer",
                        "query_type": query_type,
                        "time": elapsed,
                        "success": True
                    })
                    print(f"Interviewer - {query_type}: {elapsed:.2f} сек")

            except Exception as e:
                elapsed = time.time() - start_time
                results.append({
                    "agent": "coordinator",
                    "query_type": query_type,
                    "time": elapsed,
                    "success": False,
                    "error": str(e)
                })

        # Анализ результатов
        successful_tests = [r for r in results if r["success"]]
        avg_time = sum(r["time"] for r in successful_tests) / len(successful_tests)
        max_time = max(r["time"] for r in successful_tests)
        p95_time = sorted(r["time"] for r in successful_tests)[
            int(len(successful_tests) * 0.95)
        ]

        print(f"\n{'=' * 50}")
        print("РЕЗУЛЬТАТЫ ПРОИЗВОДИТЕЛЬНОСТИ:")
        print(f"{'=' * 50}")
        print(f"Среднее время: {avg_time:.2f} сек")
        print(f"Максимальное:  {max_time:.2f} сек")
        print(f"95-й перцентиль: {p95_time:.2f} сек")
        print(f"Успешных тестов: {len(successful_tests)}/{len(results)}")
        print(f"{'=' * 50}")

        # Проверка порогов
        assert avg_time < 3.0, f"Среднее время превышает 3 сек: {avg_time:.2f}"
        assert p95_time < 4.0, f"95-й перцентиль превышает 4 сек: {p95_time:.2f}"

        # Сохраняем метрики
        pytest.performance_metrics = {
            "avg_response_time": avg_time,
            "p95_response_time": p95_time,
            "max_response_time": max_time,
            "success_rate": len(successful_tests) / len(results)
        }