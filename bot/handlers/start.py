# bot/handlers/start.py
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from db.models import SessionLocal
from bot.states import UserStates

router = Router()


class StartStates(StatesGroup):
    waiting_level_track = State()


@router.message(Command("begin"))
async def cmd_begin(message: types.Message, state: FSMContext):
    """Начать подготовку"""
    await state.set_state(StartStates.waiting_level_track)
    await message.answer(
        "<b>🎯 Начнем подготовку!</b>\n\n"
        "Укажите ваш уровень и направление:\n"
        "<code>уровень направление</code>\n\n"
        "<b>Пример:</b> <code>junior backend</code>\n"
        "<b>Уровни:</b> junior, middle, senior\n"
        "<b>Направления:</b> backend, frontend, python, java, data"
    )


@router.message(StartStates.waiting_level_track)
async def process_level_track(message: types.Message, state: FSMContext, agents: dict, use_rag: bool):
    """Обработка уровня и направления"""
    text = message.text.strip().lower()
    parts = text.split()

    if len(parts) < 2:
        await message.answer("❌ Укажите уровень И направление\nПример: <code>junior backend</code>")
        return

    level, track = parts[0], parts[1]

    # Валидация
    from bot.config import VALID_LEVELS, VALID_TRACKS
    if level not in VALID_LEVELS:
        await message.answer(f"❌ Уровень '{level}' не поддерживается")
        return

    # Сохраняем в состояние
    await state.update_data(level=level, track=track)

    # Обновляем пользователя в БД
    from db.models import SessionLocal
    from db.repository import UserRepository, SessionRepository

    with SessionLocal() as db:
        user = get_or_create_user(message, db)
        UserRepository.update_user_level_track(db, message.from_user.id, level, track)

        # Создаем сессию
        session = SessionRepository.create_session(
            db=db,
            telegram_id=message.from_user.id,
            session_type='assessment',
            agent='assessor',
            topic=f'{track} {level}'
        )

        await state.update_data(session_id=session.id)

    # Переходим к оценке
    from bot.states import UserStates

    # И используй подходящее состояние:
    await state.set_state(UserStates.waiting_for_level)  # Или другое состояние из UserStates

    await message.answer(
        f"✅ <b>Установлено: {level} {track}</b>\n\n"
        "Теперь опишите ваш опыт (2-3 предложения):\n\n"
        "<b>Пример:</b>\n"
        "Изучал Python 6 месяцев, знаю основы ООП, решал задачи на LeetCode."
    )


@router.message(UserStates.waiting_for_level)  # Убедись что это то же состояние что в строке 70
async def process_experience(message: types.Message, state: FSMContext, agents: dict, use_rag: bool):
    """Обработка описания опыта"""
    experience = message.text.strip()

    # Получаем сохраненные данные
    data = await state.get_data()
    level = data.get('level', 'junior')
    track = data.get('track', 'backend')

    # # Сохраняем опыт в БД
    # from db.models import SessionLocal
    # from db.repository import SessionRepository
    #
    # with SessionLocal() as db:
    #     if session_id:
    #         SessionRepository.update_session_data(db, session_id, {"experience": experience})

    # Обработка через assessor если доступен
    response = f"✅ <b>Спасибо за описание опыта!</b>\n\n"

    if agents and "assessor" in agents and agents["assessor"]:
        try:
            assessor = agents["assessor"]
            # Создаем оценку
            assessment = assessor.create_assessment(experience, level, track)

            if hasattr(assessment, 'level'):
                response += f"📊 <b>Оценка:</b> {assessment.level}\n"
            if hasattr(assessment, 'confidence'):
                confidence = assessment.confidence * 100
                response += f"📈 <b>Уверенность:</b> {confidence:.0f}%\n"

            if hasattr(assessment, 'recommendations') and assessment.recommendations:
                response += f"\n📝 <b>Рекомендации:</b>\n"
                for i, rec in enumerate(assessment.recommendations[:2], 1):
                    response += f"{i}. {rec}\n"

        except Exception as e:
            print(f"Ошибка оценки: {e}")
            response += "📊 <b>Ваш опыт:</b> соответствует уровню Junior\n"

    response += "\n<b>Что дальше?</b>\n"
    response += "• /assess - полная оценка навыков\n"
    response += "• /plan - создать план обучения\n"
    response += "• /interview - пройти собеседование\n"
    response += "• /review - проверить код\n\n"
    response += "<i>Или просто задавайте вопросы!</i>"

    await message.answer(response, parse_mode="HTML")
    await state.clear()


def get_or_create_user(message, db):
    """Получает или создает пользователя"""
    from db.repository import UserRepository
    return UserRepository.get_or_create_user(
        db=db,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )


def register_start_handlers(dp, agents: dict, use_rag: bool):
    """Регистрация стартовых хэндлеров"""
    dp.include_router(router)