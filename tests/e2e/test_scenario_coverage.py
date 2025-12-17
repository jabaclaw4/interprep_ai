# tests/e2e/test_scenario_coverage.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from agents.interviewer_agent import InterviewerAgent
from rag.retriever import get_questions_by_topic


class TestScenarioCoverage:
    """Тесты для метрики разнообразия сценариев."""

    @pytest.mark.asyncio
    async def test_topic_coverage(self, interviewer_agent):
        """Проверка покрытия заявленных тем."""
        expected_topics = {
            "python": ["ООП", "декораторы", "генераторы", "исключения", "типизация"],
            "algorithms": ["сортировка", "поиск", "сложность", "структуры", "графы"],
            "databases": ["SQL", "индексы", "транзакции", "нормализация", "оптимизация"]
        }

        coverage_results = {}

        # Мокаем RAG retriever для возврата тестовых вопросов
        test_questions = [
            {
                "question": "Что такое {}?",
                "answer": "Это важная концепция в программировании",
                "topic": "test",
                "difficulty": "easy",
                "level": "junior",
                "metadata": {}
            }
        ]

        for topic, subtopics in expected_topics.items():
            print(f"\nПроверка темы: {topic.upper()}")

            covered_subtopics = 0

            for subtopic in subtopics:
                try:
                    # Мокаем get_questions_by_topic для каждой подтемы
                    with patch('rag.retriever.get_questions_by_topic') as mock_get_questions:
                        # Генерируем релевантные вопросы для подтемы
                        relevant_question = test_questions.copy()
                        relevant_question[0]["question"] = f"Что такое {subtopic}?"
                        relevant_question[0]["topic"] = topic
                        mock_get_questions.return_value = relevant_question

                        # Если у interviewer_agent есть атрибут retriever, мокаем его
                        if hasattr(interviewer_agent, 'retriever'):
                            interviewer_agent.retriever.get_questions_by_topic = Mock(
                                return_value=relevant_question
                            )

                        # Также мокаем прямое обращение к функции, если оно используется
                        with patch('rag.retriever.get_questions_by_topic',
                                   return_value=relevant_question):

                            # Запрашиваем вопросы по подтеме
                            # Пробуем разные возможные сигнатуры метода
                            try:
                                # Вариант 1: generate_questions с topic
                                questions = await interviewer_agent.generate_questions(
                                    topic=f"{topic} {subtopic}",
                                    count=3
                                )
                            except TypeError:
                                try:
                                    # Вариант 2: generate_questions без count
                                    questions = await interviewer_agent.generate_questions(
                                        topic=f"{topic} {subtopic}"
                                    )
                                except TypeError:
                                    # Вариант 3: другой метод
                                    questions = await interviewer_agent.generate_question(
                                        topic=f"{topic} {subtopic}"
                                    )

                        # Проверяем, что вопросы релевантны
                        if questions:
                            # Если questions - список
                            if isinstance(questions, list):
                                first_question = questions[0] if questions else ""
                            else:
                                first_question = str(questions)

                            is_relevant = self._check_topic_relevance(
                                first_question, subtopic
                            )
                            if is_relevant:
                                covered_subtopics += 1
                                print(f"  ✓ {subtopic}")
                            else:
                                print(f"  ✗ {subtopic} (нерелевантно: {first_question[:50]}...)")
                        else:
                            print(f"  ✗ {subtopic} (нет вопросов)")

                except Exception as e:
                    print(f"  ✗ {subtopic} (ошибка: {str(e)[:50]}...)")

            coverage = covered_subtopics / len(subtopics) if subtopics else 0
            coverage_results[topic] = coverage

            print(f"Покрытие: {coverage:.1%}")

        # Проверяем минимальное покрытие
        for topic, coverage in coverage_results.items():
            assert coverage >= 0.6, f"Тема {topic} покрыта недостаточно: {coverage:.1%}"

        # Сохраняем результаты
        pytest.coverage_metrics = {
            "topics_covered": len(expected_topics),
            "coverage_by_topic": coverage_results,
            "total_subtopics": sum(len(s) for s in expected_topics.values())
        }

        # Выводим сводку
        print(f"\n{'=' * 60}")
        print("ИТОГ ПОКРЫТИЯ ТЕМ:")
        for topic, coverage in coverage_results.items():
            status = "✅" if coverage >= 0.8 else "⚠️" if coverage >= 0.6 else "❌"
            print(f"{status} {topic.upper():15} {coverage:.1%}")
        print(f"{'=' * 60}")

    def _check_topic_relevance(self, question, subtopic):
        """Проверка релевантности вопроса подтеме."""
        if not question:
            return False

        subtopic_lower = subtopic.lower()
        question_lower = str(question).lower()

        # Проверяем наличие ключевых слов подтемы
        subtopic_keywords = subtopic_lower.split()
        keyword_match = any(
            keyword in question_lower
            for keyword in subtopic_keywords
            if len(keyword) > 3
        )

        # Для коротких ключевых слов (например, "SQL")
        if not keyword_match and len(subtopic) <= 3:
            keyword_match = subtopic_lower in question_lower

        # Проверяем длину и структуру
        is_valid_question = (
                len(str(question).strip()) > 10 and
                ('?' in str(question) or 'объясни' in question_lower or 'расскажи' in question_lower)
        )

        return keyword_match and is_valid_question

    @pytest.mark.asyncio
    async def test_rag_question_retrieval_directly(self):
        """Прямой тест получения вопросов через RAG."""
        # Тестируем напрямую функции из вашего RAG модуля
        test_cases = [
            ("Python", None, 3),
            ("Алгоритмы", "easy", 2),
            ("Базы данных", "medium", 5)
        ]

        for topic, difficulty, limit in test_cases:
            print(f"\nТестируем RAG для темы: {topic}")

            # Мокаем векторное хранилище
            with patch('rag.retriever.get_vectorstore') as mock_get_vs:
                mock_vs = Mock()
                mock_vs.query = Mock(return_value={
                    'documents': [[
                        f'Вопрос: Что такое {topic}?\nОтвет: Это важная тема в программировании',
                        f'Вопрос: Объясни основные концепции {topic}\nОтвет: Основные концепции...'
                    ]],
                    'metadatas': [[
                        {'type': 'interview_question', 'topic': topic, 'difficulty': difficulty or 'easy'},
                        {'type': 'interview_question', 'topic': topic, 'difficulty': difficulty or 'medium'}
                    ]]
                })
                mock_get_vs.return_value = mock_vs

                # Получаем вопросы через RAG
                questions = get_questions_by_topic(
                    topic=topic,
                    difficulty=difficulty,
                    limit=limit
                )

                print(f"  Найдено вопросов: {len(questions)}")

                # Проверяем что вопросы содержат тему
                relevant_count = 0
                for q in questions:
                    if topic.lower() in q['question'].lower() or topic.lower() in q['answer'].lower():
                        relevant_count += 1

                relevance_rate = relevant_count / len(questions) if questions else 0
                print(f"  Релевантность: {relevance_rate:.1%}")

                # Проверяем что получили хотя бы 1 вопрос
                assert len(questions) > 0, f"RAG не вернул вопросы для темы {topic}"
                assert relevance_rate >= 0.7, f"Низкая релевантность вопросов: {relevance_rate:.1%}"

    @pytest.mark.asyncio
    async def test_topic_diversity_across_agents(self, interviewer_agent, assessor_agent, planner_agent):
        """Тест разнообразия тем для разных агентов."""
        agents = {
            "interviewer": interviewer_agent,
            "assessor": assessor_agent,
            "planner": planner_agent
        }

        topics = ["Python ООП", "Алгоритмы сортировки", "Базы данных SQL"]

        results = {}

        for agent_name, agent in agents.items():
            print(f"\nТестируем агента: {agent_name.upper()}")

            agent_results = {}
            for topic in topics:
                try:
                    if agent_name == "interviewer":
                        # Мокаем получение вопросов
                        with patch('rag.retriever.get_questions_by_topic') as mock_get:
                            mock_get.return_value = [{
                                "question": f"Вопрос про {topic}",
                                "answer": f"Ответ про {topic}",
                                "topic": topic.split()[0],
                                "difficulty": "medium"
                            }]

                            response = await agent.generate_questions(topic=topic, count=2)

                    elif agent_name == "assessor":
                        # Для ассессора тестируем оценку
                        response = await agent.assess_answer(
                            question=f"Вопрос про {topic}",
                            answer=f"Пользователь ответил про {topic}"
                        )

                    elif agent_name == "planner":
                        # Для планировщика тестируем создание плана
                        response = await agent.create_plan(
                            topics=[topic],
                            days=3
                        )

                    # Проверяем релевантность ответа теме
                    if response:
                        relevance = self._check_topic_relevance(str(response), topic.split()[0])
                        agent_results[topic] = relevance
                        print(f"  {topic}: {'✓' if relevance else '✗'}")
                    else:
                        agent_results[topic] = False
                        print(f"  {topic}: ✗ (нет ответа)")

                except Exception as e:
                    agent_results[topic] = False
                    print(f"  {topic}: ✗ (ошибка: {str(e)[:30]})")

            # Вычисляем успешность для агента
            success_rate = sum(1 for v in agent_results.values() if v) / len(agent_results)
            results[agent_name] = success_rate

            print(f"  Успешность: {success_rate:.1%}")

        # Проверяем что все агенты работают с разными темами
        print(f"\n{'=' * 60}")
        print("ИТОГ ПО АГЕНТАМ:")
        for agent_name, success_rate in results.items():
            assert success_rate >= 0.6, f"Агент {agent_name} плохо работает с темами: {success_rate:.1%}"
            status = "✅" if success_rate >= 0.8 else "⚠️" if success_rate >= 0.6 else "❌"
            print(f"{status} {agent_name.upper():15} {success_rate:.1%}")
        print(f"{'=' * 60}")