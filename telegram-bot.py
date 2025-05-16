from admin_only import BOT_TOKEN
from database import authenticate_user
from request_parser import *

from telegram import (InlineKeyboardButton,
                      InlineKeyboardMarkup)

from telegram.ext import (MessageHandler,
                          CommandHandler,
                          ApplicationBuilder,
                          CallbackQueryHandler,
                          filters)


# Создаем глобальную переменную для хранения информации о пользователях
user_data = {}

# Переменная для хранения команд. Значения - списки словарей, где
# Ключи - названия параметров для добавления кнопка, а значения - значения этих параметров
commands = {
    'учитель': [
        {'text': 'Новые работы', 'callback_data': 'new_submissions'},
        {'text': 'Ведомость оценок', 'callback_data': 'class_grades'}
    ],
    'ученик': [
        {'text': 'Новые задания', 'callback_data': 'new_tasks'},
        {'text': 'Проверенные задания', 'callback_data': 'assessed_tasks'},
        {'text': 'Оценки', 'callback_data': 'grades'}
    ]
}


def create_command_keyboard(user_id):
    role = user_data[user_id]['role']
    keyboard = []

    # Добавляем основные команды
    for command in commands[role]:
        keyboard.append([InlineKeyboardButton(command['text'], callback_data=command['callback_data'])])

    # Добавляем кнопку "Выйти" внизу
    keyboard.append([InlineKeyboardButton("⬅️ Выйти", callback_data='logout')])

    return InlineKeyboardMarkup(keyboard)


async def help_command(update, context):
    user_id = update.effective_user.id

    if user_id not in user_data:
        await update.message.reply_text("Начни диалог при помощи команды /start")

    elif 'authenticated' not in user_data[user_id]:
        await update.message.reply_text("Зайди в свой аккаунт, чтобы получить доступ к полезным функциям! "
                                        "Если нет аккаунта, зарегистрируйся на нашей платформе "
                                        "https://127.0.0.1:8080")

    else:
        await update.message.reply_text(f"Для вас доступны следующие команды:",
                                        reply_markup=create_command_keyboard(user_id))


async def start(update, context):
    """ Функция начала диалога с пользователем. Добавляет пользователя в словарь и узнает его роль. """
    # Узнаем идентификатор пользователя
    user_id = update.effective_user.id

    # Сохраняем пользователя
    user_data[user_id] = {}

    # Создаем клавиатуру с удобным выбором для пользователя
    keyboard = [
        [InlineKeyboardButton("Ученик", callback_data='ученик')],
        [InlineKeyboardButton("Учитель", callback_data='учитель')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Вы ученик или учитель?', reply_markup=reply_markup)


async def handle_messages(update, context) -> None:
    """Функция обработки сообщения пользователя в зависимости от текущего состояния."""
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    if 'state' not in user_data[user_id]:
        await update.message.reply_text("Я не понимаю такой команды. Используйте /help")
        return

    # Обработка состояния ожидания имени класса
    if user_data[user_id]['state'] == 'waiting_for_class_name':
        class_name = text
        reply_data = get_class_grades(class_name, user_data[user_id]['login'])

        if reply_data is False:
            await update.message.reply_text("Класс не найден или у вас нет к нему доступа")
        elif isinstance(reply_data, list):
            grades_list = '\n'.join(reply_data)
            await update.message.reply_text(grades_list, parse_mode='HTML')

        # Безопасное удаление состояния
        if 'state' in user_data[user_id]:
            del user_data[user_id]['state']
        return

    # Обработка состояния ожидания логина
    if user_data[user_id]['state'] == 'waiting_for_login':
        user_data[user_id]['login'] = text
        await update.message.reply_text("Теперь введите пароль:")
        user_data[user_id]['state'] = 'waiting_for_password'
        return

    # Обработка состояния ожидания пароля
    if user_data[user_id]['state'] == 'waiting_for_password':
        password = text
        login = user_data[user_id]['login']

        auth_result = authenticate_user(login, password)

        if auth_result['status'] == 'login_not_found':
            await update.message.reply_text("Неверный логин. Попробуйте еще раз")
            del user_data[user_id]['login']
            user_data[user_id]['state'] = 'waiting_for_login'
        elif auth_result['status'] == 'wrong_password':
            await update.message.reply_text("Неверный пароль. Попробуйте еще раз")
            user_data[user_id]['state'] = 'waiting_for_password'
        elif auth_result['status'] == 'account_inactive':
            await update.message.reply_text("Ваш аккаунт деактивирован. Обратитесь к администратору")
            del user_data[user_id]['state']
        elif auth_result['status'] == 'success':
            user_data[user_id]['authenticated'] = True
            user_data[user_id]['role'] = 'учитель' if auth_result['role'] == 'teacher' else 'ученик'
            await update.message.reply_text(
                f"Аутентификация успешна! Вы вошли как {user_data[user_id]['role']} {login}."
            )
            del user_data[user_id]['state']
            await update.message.reply_text(
                "Для вас доступны следующие команды:",
                reply_markup=create_command_keyboard(user_id)
            )
        return

    # Обработка состояния ожидания имени класса для ведомости оценок
    if user_data[user_id]['state'] == 'waiting_for_class_name':
        class_name = text
        reply_data = get_class_grades(class_name, user_data[user_id]['login'])

        if reply_data is False:
            await update.message.reply_text("Класс не найден или у вас нет к нему доступа")
        elif user_data[user_id]['state'] == 'waiting_for_class_name':
            class_name = text
            reply_data = get_class_grades(class_name, user_data[user_id]['login'])

            if reply_data is False:
                await update.message.reply_text("Класс не найден или у вас нет к нему доступа")
            elif isinstance(reply_data, list) and reply_data:  # Проверяем что это список и он не пустой
                grades_list = '\n'.join(reply_data)
                await update.message.reply_text(
                    grades_list,
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text("Нет данных для отображения")

            del user_data[user_id]['state']
        else:
            grades_list = '\n'.join(reply_data)
            await update.message.reply_text(
                grades_list,
                parse_mode='HTML'
            )

        del user_data[user_id]['state']
        return

# Функции команд учителей
async def new_submissions(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_data[user_id]['role'] != 'учитель':
        await query.message.reply_text("Эта команда доступна только учителям")
        return

    reply_data = get_new_submissions(user_data[user_id]['login'])

    if reply_data is False:
        await query.message.reply_text("Ошибка доступа")
    elif not reply_data:
        await query.message.reply_text("Нет работ, ожидающих проверки")
    else:
        tasks_list = '\n'.join(reply_data)
        await query.message.reply_text(
            f"<b>Работы на проверке ({len(reply_data)}):</b>\n{tasks_list}",
            parse_mode='HTML'
        )

# Функции команд учеников
async def new_tasks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_data[user_id]['role'] != 'ученик':
        await query.message.reply_text("Эта команда доступна только ученикам")
        return

    reply_data = get_new_tasks(user_data[user_id]['login'])

    if not reply_data:
        await query.message.reply_text("У вас нет новых заданий")
    else:
        tasks_list = '\n'.join(reply_data)
        await query.message.reply_text(
            f"<b>Ваши новые задания ({len(reply_data)}):</b>\n{tasks_list}",
            parse_mode='HTML'
        )

async def assessed_tasks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_data[user_id]['role'] != 'ученик':
        await query.message.reply_text("Эта команда доступна только ученикам")
        return

    reply_data = get_assessed_tasks(user_data[user_id]['login'])

    if not reply_data:
        await query.message.reply_text("Оцененных заданий нет")
    else:
        tasks_list = '\n'.join(reply_data)
        await query.message.reply_text(
            f"<b>Ваши проверенные задания ({len(reply_data)}):</b>\n{tasks_list}",
            parse_mode='HTML'
        )

async def grades(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_data[user_id]['role'] != 'ученик':
        await query.message.reply_text("Эта команда доступна только ученикам")
        return

    reply_data = get_grades(user_data[user_id]['login'])

    if not reply_data:
        await query.message.reply_text("У вас нет оценок")
    else:
        grades_list = '\n'.join(f"{task} - {grade}" for task, grade in reply_data.items())
        await query.message.reply_text(
            f"<b>Ваши оценки ({len(reply_data)}):</b>\n{grades_list}",
            parse_mode='HTML'
        )


async def class_grades_handler(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_data[user_id]['role'] != 'учитель':
        await query.message.reply_text("Эта команда доступна только учителям")
        return

    user_data[user_id]['state'] = 'waiting_for_class_name'
    await query.message.reply_text("Введите название класса:")

# Переменная соответствия callback_data и названий обработчиков
match = {
    'new_submissions': new_submissions,
    'class_grades': class_grades_handler,
    'new_tasks': new_tasks,
    'assessed_tasks': assessed_tasks,
    'grades': grades,
    'logout': lambda u, c: None
}

async def button_handler(update, context):
    """ Обрабатывает нажатия на inline-кнопки команд. """
    # Ожидаем действие пользователя
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data

    # Обработка выхода
    if callback_data == 'logout':
        user_data.pop(user_id, None)  # Удаляем данные пользователя
        await query.message.reply_text("Вы вышли из системы. Для входа используйте /start")
        return

    # Обработка выбора роли (Ученик/Учитель)
    if callback_data in ['ученик', 'учитель']:
        user_data[user_id]['role'] = callback_data  # Сохраняем роль
        await query.edit_message_text(
            text=f"Вы выбрали роль: {callback_data}. "
                 f"Теперь войдите в аккаунт (если у вас нет аккаунта, зарегистрируйтесь на веб-платформе) "
                 f"Введите логин:")
        user_data[user_id]['state'] = 'waiting_for_login'  # Устанавливаем состояние "ожидает логин"
        return  # Завершаем обработку, чтобы не перешло к командам

    # Переходим к обработке команд
    # Проверяем, аутентифицирован ли пользователь
    if user_id not in user_data or not user_data[user_id].get('authenticated'):
        await query.message.reply_text("Пожалуйста, войдите в аккаунт с помощью /start")
        return

    # Вызываем соответствующую функцию на основе callback_data
    if callback_data in match:
        await match[callback_data](update, context)

    else:
        await query.message.reply_text("Неизвестная команда.")

async def class_grades(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_data[user_id]['role'] != 'учитель':
        await query.message.reply_text("Эта команда доступна только учителям")
        return

    user_data[user_id]['state'] = 'waiting_for_class_name'
    await query.message.reply_text("Введите название класса:")



def main():
    """ Функция запуска бота. """
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Обработчики стартовых команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Обработчик нажатия всех кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Обработчики общения с пользователем
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    # Запуск приложения
    application.run_polling()


if __name__ == '__main__':
    main()
