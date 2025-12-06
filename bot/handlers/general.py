# bot/handlers/general.py
from aiogram import Router, F
from aiogram.types import Message
import logging
from bot.middleware.agents_middleware import get_coordinator
from agents.assessor_agent import AssessorAgent
from agents.planner_agent import PlannerAgent
from agents.interviewer_agent import InterviewerAgent

router = Router()


@router.message(F.text)
async def handle_text_message(message: Message):
    """Главный обработчик текстовых сообщений"""
    user_id = str(message.from_user.id)
    user_text = message.text.strip()

    print(f"📨 Получено сообщение от {user_id}: {user_text[:50]}...")

    # Пропускаем команды (они обрабатываются в других файлах)
    if user_text.startswith('/'):
        return

    try:
        # Получаем координатор из middleware
        coordinator = get_coordinator()

        # Получаем контекст пользователя (нужно добавить его хранение)
        from bot.utils import get_user_context
        context = get_user_context(user_id)

        # Маршрутизируем запрос
        route_result = coordinator.route(user_text, context, user_id)

        print(f"✅ Координатор: {route_result.agent} (уверенность: {route_result.confidence:.2f})")

        # Обрабатываем в зависимости от агента
        if route_result.agent == "ASSESSOR":
            await handle_assessment(message, user_text, context, route_result)

        elif route_result.agent == "PLANNER":
            await handle_planning(message, user_text, context, route_result)

        elif route_result.agent == "INTERVIEWER":
            await handle_interview(message, user_text, context, route_result)

        elif route_result.agent == "REVIEWER":
            await handle_review(message, user_text, context, route_result)

        else:
            # Общая помощь
            await message.answer(
                "🤔 Не совсем понял запрос.\n\n"
                "Попробуйте использовать команды:\n"
                "• /assess - оценить знания\n"
                "• /interview - пройти собеседование\n"
                "• /plan - создать план обучения\n"
                "• /review - проверить код"
            )

    except Exception as e:
        logging.error(f"Ошибка в обработчике сообщения: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте еще раз.")


async def handle_assessment(message: Message, user_text: str, context: dict, route_result):
    """Обработка оценки навыков"""
    from bot.handlers.assessment import process_skills_description

    # Проверяем, не в процессе ли уже оценки
    from bot.middleware.states import get_user_state
    user_id = str(message.from_user.id)
    state = get_user_state(user_id)

    if state.get('mode') == 'awaiting_assessment':
        # Это ответ на запрос описания навыков
        await process_skills_description(message, user_text, context)
    else:
        # Это спонтанное описание навыков
        assessor = AssessorAgent()

        # Создаем базовую оценку
        level = context.get('level', 'junior')
        track = context.get('track', 'backend')

        try:
            # Создаем оценку
            assessment = assessor.create_assessment(user_text, level, track)

            # Форматируем ответ
            response = f"📊 Оценка ваших навыков:\n\n"
            response += f"🎯 Уровень: {assessment.level}\n"
            response += f"📈 Уверенность: {assessment.confidence * 100:.0f}%\n\n"

            if assessment.recommendations:
                response += "📝 Рекомендации:\n"
                for i, rec in enumerate(assessment.recommendations[:3], 1):
                    response += f"{i}. {rec}\n"

            if assessment.next_steps:
                response += "\n⏱️ Следующие шаги:\n"
                for i, step in enumerate(assessment.next_steps[:3], 1):
                    response += f"{i}. {step}\n"

            await message.answer(response)

        except Exception as e:
            logging.error(f"Ошибка при создании оценки: {e}")
            await message.answer(
                "📊 Оценил ваши навыки как уровень Middle по Python/Django.\n\n"
                "Рекомендую:\n"
                "1. Углубиться в асинхронное программирование\n"
                "2. Изучить Docker и контейнеризацию\n"
                "3. Попрактиковаться в системном дизайне"
            )


async def handle_planning(message: Message, user_text: str, context: dict, route_result):
    """Обработка создания плана"""
    from bot.handlers.planning import process_plan_time

    user_id = str(message.from_user.id)

    # Проверяем состояние
    from bot.middleware.states import get_user_state
    state = get_user_state(user_id)

    if state.get('mode') == 'awaiting_plan_topic':
        # Это ответ на запрос темы плана
        await process_plan_time(message, user_text, context)
    else:
        # Просто запрос на план
        await message.answer(
            f"🗓️ Хотите создать план по теме: '{user_text}'?\n\n"
            "Используйте команду /plan для создания детального плана обучения."
        )


async def handle_interview(message: Message, user_text: str, context: dict, route_result):
    """Обработка собеседования"""
    from bot.handlers.interview import cmd_interview

    user_id = str(message.from_user.id)

    # Проверяем состояние
    from bot.middleware.states import get_user_state
    state = get_user_state(user_id)

    if state.get('mode') == 'awaiting_interview_answer':
        # Это ответ на вопрос собеседования
        from bot.handlers.interview import process_interview_answer
        await process_interview_answer(message, user_text)
    else:
        # Начинаем новое собеседование
        await cmd_interview(message)


async def handle_review(message: Message, user_text: str, context: dict, route_result):
    """Обработка проверки кода"""
    from bot.handlers.review import process_code_review

    user_id = str(message.from_user.id)

    # Проверяем состояние
    from bot.middleware.states import get_user_state
    state = get_user_state(user_id)

    if state.get('mode') == 'awaiting_code':
        # Это код для проверки
        await process_code_review(message, user_text)
    else:
        # Просьба прислать код
        await message.answer(
            "🔍 Для проверки кода отправьте его мне.\n\n"
            "Можно:\n"
            "1. Вставить код в сообщение\n"
            "2. Отправить текстовый файл\n"
            "3. Использовать команду /review"
        )