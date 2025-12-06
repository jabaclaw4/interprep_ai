# bot/handlers/__init__.py
import logging
from aiogram import Router, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from ..states import UserStates
from .general import router as general_router

# ДОБАВИТЬ после импортов:
from .planning import (
    process_plan_goal,
    process_plan_level,
    process_plan_time,
    process_plan_confirmation,
    process_save_plan
)



logger = logging.getLogger(__name__)

# Создаем главный роутер
main_router = Router()


# Базовые команды
@main_router.message(Command("progress"))
async def cmd_progress(message: types.Message):
    """Показать прогресс"""
    from db.models import SessionLocal
    from db.repository import get_user_stats
    from bot.utils import get_or_create_user

    with SessionLocal() as db:
        try:
            # Получаем пользователя
            user, db = get_or_create_user(message, db)

            # Получаем статистику
            stats = get_user_stats(db, message.from_user.id)

            response = f"""
<b>📈 Ваш прогресс</b>

👤 {stats['user'].get('username', 'Аноним')}
🎯 Уровень: {stats['user'].get('level', 'junior')}
🚀 Направление: {stats['user'].get('track', 'backend')}

<b>📊 Активность:</b>
• Сессий: {sum(stats.get('sessions_by_type', {}).values())}
• Оценок: {len(stats.get('latest_assessments', []))}
"""
            await message.answer(response, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.error(f"Ошибка получения прогресса: {e}")
            await message.answer(
                "📊 Пройдите /assess чтобы начать отслеживать прогресс\n"
                "Или используйте /start для начала работы"
            )


@main_router.message(Command("plan"))
async def cmd_plan(message: types.Message, state: FSMContext):
    """План обучения"""
    print("🔴 /plan ВЫЗВАН!")
    print(f"🔴 Сообщение: {message.text}")
    print(f"🔴 User ID: {message.from_user.id}")

    await state.set_state(UserStates.waiting_goal)
    current_state = await state.get_state()
    print(f"🔴 Установлено состояние: {current_state}")

    await message.answer(
        "🗓️ <b>Создание плана обучения</b>\n\n"
        "📝 <b>Что конкретно хотите изучить?</b>\n\n"
        "<i>Примеры:</i>\n"
        "• Микросервисная архитектура с нуля\n"
        "• Docker и Kubernetes для микросервисов\n"
        "• Алгоритмы и структуры данных\n\n"
        "Напишите тему одним сообщением:",
        parse_mode=ParseMode.HTML
    )

    print("🔴 Ответ отправлен пользователю")


@main_router.message(UserStates.waiting_goal)  # Используем UserStates.waiting_goal
async def process_plan_topic(message: types.Message, state: FSMContext, agents: dict = None):
    """Обработка темы для плана - напрямую, без координатора"""
    topic = message.text.strip()

    # Сохраняем тему в состоянии
    await state.update_data(topic=topic)

    # Используем waiting_for_level для запроса уровня
    # Создаем клавиатуру для выбора уровня
    builder = ReplyKeyboardBuilder()
    builder.button(text="🟢 Начинающий")
    builder.button(text="🟡 Средний")
    builder.button(text="🔴 Продвинутый")
    keyboard = builder.as_markup(resize_keyboard=True)

    await state.set_state(UserStates.waiting_for_level)  # Используем существующее состояние

    await message.answer(
        f"🎯 <b>Отлично! Будем изучать: {topic}</b>\n\n"
        "<b>Выберите ваш текущий уровень:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@main_router.message(UserStates.waiting_for_level)  # Используем UserStates.waiting_for_level
async def process_plan_level(message: types.Message, state: FSMContext, agents: dict = None):
    """Обработка уровня для плана"""
    level_text = message.text.lower()

    # Определяем уровень по тексту
    if "начин" in level_text or "начинаю" in level_text or "начина" in level_text:
        level = "Начинающий"
    elif "средн" in level_text or "средни" in level_text:
        level = "Средний"
    elif "продви" in level_text or "продвинут" in level_text:
        level = "Продвинутый"
    else:
        level = "Средний"

    # Сохраняем уровень в состоянии
    await state.update_data(level=level)

    # Для времени используем waiting_for_hours
    # Создаем клавиатуру для выбора времени
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏳ 2-3 часа в неделю")
    builder.button(text="⏰ 5-7 часов в неделю")
    builder.button(text="⚡ 10+ часов в неделю")
    keyboard = builder.as_markup(resize_keyboard=True)

    await state.set_state(UserStates.waiting_for_hours)  # Используем существующее состояние

    await message.answer(
        f"📊 <b>Уровень: {level}</b>\n\n"
        "<b>Сколько времени готовы уделять в неделю?</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@main_router.message(UserStates.waiting_for_hours)
async def process_plan_time(
        message: types.Message,
        state: FSMContext,
        agents: dict = None
):
    """Обработка времени и создание плана"""
    time_per_week = message.text.strip()

    # Получаем все данные из состояния
    data = await state.get_data()
    topic = data.get('topic', 'Не указано')
    level = data.get('level', 'Средний')

    # Проверяем наличие planner
    if not agents or not isinstance(agents, dict):
        await message.answer(
            "❌ Ошибка системы: агенты не доступны",
            parse_mode=ParseMode.HTML,
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        return

    planner = agents.get("planner")
    if not planner:
        await message.answer(
            "❌ Ошибка: PlannerAgent не найден",
            parse_mode=ParseMode.HTML,
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()
        return

    # Сообщаем о начале создания плана
    await message.answer(
        f"🔄 <b>Создаю персонализированный план...</b>\n\n"
        f"📚 <b>Тема:</b> {topic}\n"
        f"📊 <b>Уровень:</b> {level}\n"
        f"⏱️ <b>Время:</b> {time_per_week}\n\n"
        "<i>Пожалуйста, подождите...</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ReplyKeyboardRemove()
    )

    try:
        # Получаем уровень в формате для planner (junior/middle/senior)
        level_mapping = {
            "Начинающий": "junior",
            "Средний": "middle",
            "Продвинутый": "senior"
        }
        level_for_planner = level_mapping.get(level, "middle")

        # Определяем количество недель по времени
        if "2-3" in time_per_week or "2" in time_per_week:
            weeks = 8  # дольше при малом времени
            hours_per_week = 2
        elif "5-7" in time_per_week:
            weeks = 6
            hours_per_week = 6
        else:
            weeks = 4  # быстрее при большом времени
            hours_per_week = 10

        # Создаем план через PlannerAgent
        # Проверяем какой метод есть у planner
        if hasattr(planner, 'make_plan'):
            # Если метод называется make_plan
            plan_result = planner.make_plan(
                user_text=topic,
                level=level_for_planner,
                track="general",  # общее направление
                weeks=weeks,
                goals=f"Изучить {topic} за {weeks} недель"
            )
        elif hasattr(planner, 'create_plan'):
            # Если метод называется create_plan
            plan_result = planner.create_plan({
                'user_text': topic,
                'level': level_for_planner,
                'weeks': weeks,
                'goals': f"Изучить {topic}"
            })
        else:
            # Fallback
            plan_result = None

        # Форматируем ответ
        if plan_result:
            # Если plan_result объект с методом dict()
            if hasattr(plan_result, 'dict'):
                plan_data = plan_result.dict()
            elif isinstance(plan_result, dict):
                plan_data = plan_result
            else:
                plan_data = {'summary': str(plan_result)}

            # Форматируем план
            response = f"""
✅ <b>План обучения создан!</b>

🎯 <b>Тема:</b> {topic}
📊 <b>Уровень:</b> {level}
⏱️ <b>Время:</b> {time_per_week}
📅 <b>Длительность:</b> {plan_data.get('total_weeks', weeks)} недель

📝 <b>Что будете изучать:</b>
{', '.join(plan_data.get('focus_areas', [topic, 'основные концепции']))}

{plan_data.get('summary', 'Персонализированный план обучения.')[:300]}...

<b>Хотите сохранить этот план?</b>
"""

            # Сохраняем план в состоянии
            await state.update_data(
                plan_content=str(plan_result),
                plan_data=plan_data,
                time=time_per_week,
                weeks=plan_data.get('total_weeks', weeks)
            )
        else:
            # Fallback если planner не вернул результат
            response = f"""
✅ <b>План обучения создан!</b>

🎯 <b>Тема:</b> {topic}
📊 <b>Уровень:</b> {level}
⏱️ <b>Время:</b> {time_per_week}
📅 <b>Длительность:</b> {weeks} недель

📋 <b>Структура плана:</b>
Неделя 1-2: Основные концепции {topic}
Неделя 3-4: Углубленное изучение
Неделя 5-6: Практическое применение
Неделя 7-{weeks}: Проектная работа и закрепление

<b>Хотите сохранить этот план?</b>
"""

            await state.update_data(
                plan_content=response,
                time=time_per_week,
                weeks=weeks
            )

        # Создаем клавиатуру для сохранения
        builder = ReplyKeyboardBuilder()
        builder.button(text="✅ Да, сохранить план")
        builder.button(text="❌ Нет, не сохранять")
        keyboard = builder.as_markup(resize_keyboard=True)

        # Переходим в состояние создания плана
        await state.set_state(UserStates.creating_plan)

        await message.answer(
            response,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка при создании плана: {e}")
        import traceback
        traceback.print_exc()

        # Fallback ответ
        response = f"""
✅ <b>План по изучению {topic}</b>

📊 <b>Уровень:</b> {level}
⏱️ <b>Время:</b> {time_per_week}

📋 <b>Примерный план на 6 недель:</b>

<b>Неделя 1-2:</b> Основные концепции
- Теория и базовые принципы
- Простые примеры

<b>Неделя 3-4:</b> Углубленное изучение  
- Паттерны и best practices
- Решение задач

<b>Неделя 5-6:</b> Практика
- Мини-проект
- Завершение обучения

<b>Хотите сохранить этот план?</b>
"""

        # Создаем клавиатуру
        builder = ReplyKeyboardBuilder()
        builder.button(text="✅ Да, сохранить план")
        builder.button(text="❌ Нет, не сохранять")
        keyboard = builder.as_markup(resize_keyboard=True)

        await state.set_state(UserStates.creating_plan)
        await state.update_data(plan_content=response, time=time_per_week)

        await message.answer(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)

@main_router.message(UserStates.creating_plan)  # Используем UserStates.creating_plan
async def process_save_plan_choice(message: types.Message, state: FSMContext):
    """Обработка выбора сохранения плана"""
    from db.models import SessionLocal
    from db.repository import PlanRepository
    from bot.utils import get_or_create_user

    choice = message.text.lower()

    if "да" in choice or "сохран" in choice:
        try:
            data = await state.get_data()
            topic = data.get('topic', 'Неизвестная тема')
            plan_content = data.get('plan_content', '')
            level = data.get('level', 'Средний')
            time_per_week = data.get('time', 'Не указано')

            with SessionLocal() as db:
                user, db = get_or_create_user(message, db)

                plan_data = {
                    'title': f'План: {topic}',
                    'description': plan_content[:200] + '...' if len(plan_content) > 200 else plan_content,
                    'track': user.current_track or 'backend',
                    'level': level,
                    'duration_weeks': 6,  # По умолчанию 6 недель
                    'plan_data': {
                        'topic': topic,
                        'level': level,
                        'time': time_per_week,
                        'content': plan_content
                    },
                    'progress': 0.0
                }

                PlanRepository.save_learning_plan(db, message.from_user.id, plan_data)

                await message.answer(
                    "✅ <b>План успешно сохранен!</b>\n\n"
                    "Вы можете посмотреть его в любой момент через команду /progress",
                    parse_mode=ParseMode.HTML,
                    reply_markup=types.ReplyKeyboardRemove()
                )

        except Exception as e:
            logger.error(f"Ошибка сохранения плана: {e}")
            await message.answer(
                f"❌ <b>Ошибка при сохранении плана:</b>\n{str(e)[:200]}",
                parse_mode=ParseMode.HTML
            )
    else:
        await message.answer(
            "✅ Хорошо, план не сохранен.",
            parse_mode=ParseMode.HTML,
            reply_markup=types.ReplyKeyboardRemove()
        )

    await state.clear()


@main_router.message(Command("review"))
async def cmd_review(message: types.Message):
    """Code review"""
    await message.answer(
        "<b>🔍 Code Review</b>\n\n"
        "Отправьте код в формате:\n"
        "<pre><code class=\"language-python\">"
        "def example():\n"
        "    return 'Hello'"
        "</code></pre>\n\n"
        "Я проанализирую его и дам рекомендации.",
        parse_mode=ParseMode.HTML
    )


@main_router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Справка"""
    help_text = """
🤖 <b>InterPrep AI - помощник для подготовки к собеседованиям</b>

<b>Основные команды:</b>
/start - Начать работу
/help - Эта справка
/progress - Ваш прогресс
/plan - План обучения
/review - Проверить код

<b>Режимы работы:</b>
/assess - Оценка навыков
/interview - Тренировка собеседования

<b>Просто отправьте:</b>
• Вопрос по программированию
• Код для анализа
• Запрос на помощь с подготовкой
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@main_router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Старт бота"""
    await message.answer(
        "🤖 <b>InterPrep AI v1.0</b>\n\n"
        "Интеллектуальный помощник для подготовки к IT-собеседованиям.\n\n"
        "Используйте /help для списка команд.",
        parse_mode=ParseMode.HTML
    )


@main_router.message(Command("interview"))
async def cmd_interview(message: types.Message, agents: dict, use_rag: bool):
    """Начать собеседование"""
    try:
        # Проверяем, есть ли агент interviewer
        if "interviewer" in agents and agents["interviewer"]:
            await message.answer(
                "<b>💬 Начинаем собеседование!</b>\n\n"
                "Сейчас я задам вам несколько вопросов.\n\n"
                "Используйте /cancel для завершения.",
                parse_mode=ParseMode.HTML
            )

            # Здесь будет логика собеседования
            # Пока просто тестовый ответ
            await message.answer(
                "Расскажите о вашем опыте работы с Python.\n\n"
                "Сколько лет опыта и какие проекты вы реализовывали?"
            )
        else:
            await message.answer(
                "⚠️ <b>Агент собеседования временно недоступен</b>\n\n"
                "Сейчас я могу помочь:\n"
                "• Ответить на вопросы по программированию\n"
                "• Проверить код\n"
                "• Помочь с подготовкой\n\n"
                "Просто напишите ваш запрос.",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Ошибка в команде interview: {e}")
        await message.answer(
            "🤖 Используйте команды:\n"
            "/start - начало работы\n"
            "/help - помощь\n"
            "/progress - ваш прогресс"
        )


@main_router.message(Command("assess"))
async def cmd_assess(message: types.Message, agents: dict, use_rag: bool):
    """Оценка навыков"""
    try:
        if "assessor" in agents and agents["assessor"]:
            await message.answer(
                "<b>📊 Оценка навыков</b>\n\n"
                "Чтобы оценить ваши знания, ответьте на несколько вопросов.\n\n"
                "<b>Или опишите:</b>\n"
                "• Какие технологии вы знаете\n"
                "• Ваш уровень опыта\n"
                "• Над какими проектами работали\n\n"
                "Пример: <code>Знаю Python, Django, 2 года опыта, работал над API и веб-приложениями</code>",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                "📊 <b>Опишите ваши навыки:</b>\n\n"
                "• Языки программирования\n"
                "• Фреймворки\n"
                "• Уровень опыта\n"
                "• Проекты\n\n"
                "<i>Пример: Python, Django, 2 года, веб-приложения</i>",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Ошибка в команде assess: {e}")
        await message.answer("📊 Просто опишите ваши навыки и опыт работы.")


@main_router.message(Command("begin"))
async def cmd_begin(message: types.Message):
    """Начать подготовку с указанием уровня и направления"""
    try:
        # Разбираем аргументы команды
        args = message.text.split()[1:]  # Пропускаем "/begin"

        if len(args) < 2:
            await message.answer(
                "<b>🎯 Начнем подготовку!</b>\n\n"
                "<b>Формат:</b> <code>/begin [уровень] [направление]</code>\n\n"
                "<b>Уровни:</b> junior, middle, senior\n"
                "<b>Направления:</b> backend, frontend, python, java, data, devops, fullstack\n\n"
                "<b>Пример:</b> <code>/begin junior backend</code>\n"
                "<b>Пример:</b> <code>/begin middle python</code>",
                parse_mode=ParseMode.HTML
            )
            return

        level = args[0].lower()
        track = args[1].lower()

        from bot.config import VALID_LEVELS, VALID_TRACKS

        if level not in VALID_LEVELS:
            await message.answer(
                f"❌ <b>Неверный уровень:</b> {level}\n"
                f"<b>Доступные уровни:</b> {', '.join(VALID_LEVELS)}",
                parse_mode=ParseMode.HTML
            )
            return

        if track not in VALID_TRACKS:
            await message.answer(
                f"❌ <b>Неверное направление:</b> {track}\n"
                f"<b>Доступные направления:</b> {', '.join(VALID_TRACKS)}",
                parse_mode=ParseMode.HTML
            )
            return

        # Сохраняем настройки пользователя
        from db.models import SessionLocal
        from db.repository import UserRepository

        with SessionLocal() as db:
            user = UserRepository.get_or_create_user(db, message.from_user.id)
            UserRepository.update_user_level_track(db, message.from_user.id, level, track)

        await message.answer(
            f"✅ <b>Отлично!</b>\n\n"
            f"🎯 <b>Уровень:</b> {level}\n"
            f"🚀 <b>Направление:</b> {track}\n\n"
            f"Теперь вы можете:\n"
            f"• <code>/assess</code> - оценить знания\n"
            f"• <code>/interview</code> - пройти собеседование\n"
            f"• <code>/plan</code> - создать план обучения\n"
            f"• <code>/review</code> - проверить код\n\n"
            f"<i>Или просто пишите вопросы по программированию!</i>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Ошибка в команде begin: {e}")
        await message.answer(
            "🤖 Используйте: <code>/begin [уровень] [направление]</code>\n\n"
            "Пример: <code>/begin junior backend</code>",
            parse_mode=ParseMode.HTML
        )


def register_handlers(dp: Dispatcher, agents: dict, use_rag: bool):
    """
    Регистрация всех хэндлеров в aiogram 3.x

    Args:
        dp: Диспетчер aiogram
        agents: Словарь с агентами
        use_rag: Флаг использования RAG
    """
    # Включаем все роутеры
    dp.include_router(main_router)
    dp.include_router(general_router)

    logger.info("✅ Обработчики зарегистрированы")
