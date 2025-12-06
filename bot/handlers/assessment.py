# bot/handlers/assessment.py
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
import logging
from agents.assessor_agent import AssessorAgent
from bot.middleware.states import set_user_state, get_user_state, clear_user_state
from bot.middleware.agents_middleware import get_coordinator

router = Router()


class AssessmentStates(StatesGroup):
    waiting_skills = State()
    in_assessment = State()


@router.message(Command("assess"))
async def cmd_assess(message: types.Message, state: FSMContext):
    """Обработка команды /assess - БЫСТРАЯ ОЦЕНКА"""
    user_id = str(message.from_user.id)

    # Устанавливаем состояние в FSM
    await state.set_state(AssessmentStates.waiting_skills)
    await state.update_data(assessment_step=0, skills_text="")

    # Также устанавливаем состояние в нашем менеджере
    set_user_state(user_id, {
        'mode': 'awaiting_assessment',
        'step': 'describe_skills',
        'fsm_state': 'waiting_skills'
    })

    # Обновляем состояние в координаторе
    coordinator = get_coordinator()
    coordinator.set_user_state(user_id, 'awaiting_assessment_details')

    # Отправляем запрос на описание навыков
    await message.answer(
        "📊 <b>Быстрая оценка знаний</b>\n\n"
        "Опишите свои навыки и опыт (2-3 предложения):\n\n"
        "<i>Пример:</i>\n"
        "Знаю Python, ООП, работал со списками и словарями, решал задачи на сортировку.\n"
        "Или: Знаю Django, REST API, PostgreSQL, 1 год опыта backend-разработки."
    )


@router.message(AssessmentStates.waiting_skills)
async def process_skills_description(
        message: types.Message,
        state: FSMContext,
        agents: dict = None  # ← получаем словарь агентов из middleware
):
    """Обработка описания навыков пользователя"""
    user_id = str(message.from_user.id)
    user_text = message.text.strip()

    # Очищаем состояния
    await state.clear()
    clear_user_state(user_id)

    # Получаем контекст пользователя
    from bot.utils import ensure_user_context
    context = ensure_user_context(user_id)

    # Создаем оценку
    try:
        # ИСПРАВЛЕНИЕ: используем агента из словаря, а не создаем новый
        if agents and isinstance(agents, dict) and "assessor" in agents:
            assessor = agents["assessor"]
            print(f"✅ Используем существующий AssessorAgent из словаря")
        else:
            # Fallback: создаем нового если не передан словарь
            from agents.assessor_agent import AssessorAgent
            assessor = AssessorAgent()
            print(f"⚠️ Создаем новый AssessorAgent (agents не передан)")

        # Получаем уровень и направление из контекста или используем по умолчанию
        level = context.get('level', 'junior')
        track = context.get('track', 'backend')

        # Создаем оценку - вызываем метод assess() а не create_assessment()
        # Проверяем какие методы есть у твоего AssessorAgent
        if hasattr(assessor, 'create_assessment'):
            assessment = assessor.create_assessment(user_text, level, track)
        elif hasattr(assessor, 'assess'):
            # Если метод называется assess
            assessment = assessor.assess(
                answer=user_text,
                topics=["программирование", track, "алгоритмы"],
                user_context={'level': level, 'track': track}
            )
        else:
            # Если метод называется как-то иначе
            raise AttributeError("AssessorAgent не имеет методов create_assessment или assess")

        # Форматируем ответ
        response = f"📊 <b>Результаты оценки</b>\n\n"

        # Проверяем тип assessment (может быть dict или объект)
        if hasattr(assessment, 'level'):
            response += f"🎯 <b>Уровень:</b> {assessment.level}\n"
        elif isinstance(assessment, dict) and 'level' in assessment:
            response += f"🎯 <b>Уровень:</b> {assessment['level']}\n"
        elif hasattr(assessment, 'scores') and isinstance(assessment.scores, dict):
            # Если есть scores в объекте AssessResult
            scores = assessment.scores
            if 'interview_readiness' in scores:
                readiness = scores['interview_readiness']
                response += f"🎯 <b>Готовность к собеседованию:</b> {readiness}/100\n"

        if hasattr(assessment, 'confidence'):
            confidence_percent = assessment.confidence * 100
            response += f"📈 <b>Уверенность:</b> {confidence_percent:.0f}%\n"

        response += "\n"

        # Сильные стороны
        strengths = None
        if hasattr(assessment, 'strengths'):
            strengths = assessment.strengths
        elif hasattr(assessment, 'strong_points'):
            strengths = assessment.strong_points
        elif isinstance(assessment, dict) and 'strengths' in assessment:
            strengths = assessment['strengths']

        if strengths:
            response += "✅ <b>Сильные стороны:</b>\n"
            for strength in strengths[:3]:
                response += f"• {strength}\n"
            response += "\n"

        # Области для улучшения
        weaknesses = None
        if hasattr(assessment, 'weaknesses'):
            weaknesses = assessment.weaknesses
        elif hasattr(assessment, 'weak_points'):
            weaknesses = assessment.weak_points
        elif hasattr(assessment, 'weak_topics'):
            weaknesses = assessment.weak_topics
        elif isinstance(assessment, dict):
            if 'weaknesses' in assessment:
                weaknesses = assessment['weaknesses']
            elif 'weak_topics' in assessment:
                weaknesses = assessment['weak_topics']

        if weaknesses:
            response += "⚠️ <b>Области для улучшения:</b>\n"
            for weakness in weaknesses[:3]:
                response += f"• {weakness}\n"
            response += "\n"

        # Рекомендации
        recommendations = None
        if hasattr(assessment, 'recommendations'):
            recommendations = assessment.recommendations
        elif hasattr(assessment, 'feedback'):
            # feedback может содержать рекомендации
            recommendations = [assessment.feedback]
        elif isinstance(assessment, dict) and 'recommendations' in assessment:
            recommendations = assessment['recommendations']

        if recommendations:
            response += "📝 <b>Рекомендации:</b>\n"
            for i, rec in enumerate(recommendations[:3], 1):
                response += f"{i}. {rec}\n"
            response += "\n"

        # Следующие шаги
        if hasattr(assessment, 'next_steps'):
            response += "⏱️ <b>Следующие шаги:</b>\n"
            for i, step in enumerate(assessment.next_steps[:2], 1):
                response += f"{i}. {step}\n"
        elif hasattr(assessment, 'follow_up'):
            response += f"⏱️ <b>Следующий шаг:</b> {assessment.follow_up}\n"

        # Добавляем предложение создать план
        response += "\n💡 Хотите создать план обучения? Используйте <b>/plan</b>"

        await message.answer(response, parse_mode="HTML")

        # Сохраняем результат оценки в базу
        await save_assessment_result(user_id, user_text, assessment)

    except Exception as e:
        logging.error(f"Ошибка при оценке навыков: {e}", exc_info=True)

        # Fallback ответ
        await message.answer(
            "✅ <b>Получил ваше описание навыков!</b>\n\n"
            "На основе вашего опыта рекомендую:\n"
            "1. Углубить знания в архитектуре\n"
            "2. Попрактиковать алгоритмы на LeetCode\n"
            "3. Изучить Docker и CI/CD\n\n"
            "Хотите создать план обучения? Используйте <b>/plan</b>",
            parse_mode="HTML"
        )
async def save_assessment_result(user_id: str, skills_text: str, assessment):
    """Сохраняет результат оценки в базу"""
    try:
        from db.models import SessionLocal
        from db.repository import SessionRepository, AssessmentRepository

        with SessionLocal() as db:
            # Получаем или создаем пользователя
            from db.repository import UserRepository
            user = UserRepository.get_or_create_user(
                db=db,
                telegram_id=int(user_id),
                username=None,  # Можно получить из контекста
                first_name="User",
                last_name=user_id
            )

            # Создаем сессию оценки
            session = SessionRepository.create_session(
                db=db,
                telegram_id=int(user_id),
                session_type='quick_assessment',
                agent='assessor',
                topic='Quick Assessment'
            )

            # Сохраняем оценку
            if hasattr(assessment, 'to_dict'):
                assessment_data = assessment.to_dict()
            else:
                assessment_data = {
                    'level': getattr(assessment, 'level', 'unknown'),
                    'confidence': getattr(assessment, 'confidence', 0.5),
                    'skills_text': skills_text[:500]
                }

            # Сохраняем в базу (если есть репозиторий)
            if hasattr(AssessmentRepository, 'create_assessment'):
                AssessmentRepository.create_assessment(
                    db=db,
                    session_id=session.id,
                    assessment_type='skills_self_report',
                    score=getattr(assessment, 'confidence', 0.5),
                    details=assessment_data
                )

    except Exception as e:
        logging.error(f"Ошибка при сохранении оценки: {e}")


@router.message(F.text & ~F.text.startswith('/'))
async def handle_assessment_like_text(message: types.Message, state: FSMContext):
    """Обработка текста, который может быть описанием навыков (для общего роутера)"""
    # Эта функция будет вызываться из общего обработчика
    # Не нужно дублировать логику здесь

    # Проверяем, не находится ли пользователь в процессе оценки
    current_state = await state.get_state()
    if current_state == AssessmentStates.waiting_skills.state:
        # Если пользователь в состоянии ожидания навыков,
        # то сообщение обработается в process_skills_description
        return

    # Иначе пропускаем - обработка будет в общем роутере
    pass


def register_assessment_handlers(dp, agents: dict, use_rag: bool):
    """Регистрация хэндлеров оценки (для обратной совместимости)"""
    # Эта функция может быть не нужна, если используем aiogram 3.x
    # Оставляем для совместимости
    dp.include_router(router)

    # Сохраняем агенты в роутер если нужно
    if hasattr(router, '__agents__'):
        router.__agents__ = agents
        router.__use_rag__ = use_rag