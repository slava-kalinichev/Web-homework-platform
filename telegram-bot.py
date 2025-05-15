from admin_only import BOT_TOKEN
from database import authenticate_user

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


async def help_command(update, context):
    await update.message.reply_text("Зайди в свой аккаунт, чтобы получить доступ к полезным функциям! https://127.0.0.1:8080")


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


async def authentication(update, context) -> None:
    """ Функция обработки сообщения пользователя в зависимости от текущего состояния."""
    user_id = update.effective_user.id
    text = update.message.text

    # Проверяем, зарегистрирован ли идентификатор пользователя в боте
    if user_id not in user_data or 'state' not in user_data[user_id]:
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    # Если пользователь есть, начинаем проводить авторизацию.
    # Проверяем на состояние ожидания логина
    if user_data[user_id]['state'] == 'waiting_for_login':
        user_data[user_id]['login'] = text
        await update.message.reply_text("Теперь введите пароль:")

        # Устанавливаем статус "ожидает пароль"
        user_data[user_id]['state'] = 'waiting_for_password'

    # Проверяем на состояние ожидания пароля
    elif user_data[user_id]['state'] == 'waiting_for_password':
        password = text
        login = user_data[user_id]['login']

        # Проверяем, существует ли такой пользователь
        if not authenticate_user(login, password):
            # Если нет, просто сразу же выходим из обработки
            await update.message.reply_text("Неверный логин или пароль. Попробуйте еще раз")
            del user_data[user_id]['login']  # Сбрасываем данные пользователя
            user_data[user_id]['state'] = 'waiting_for_login'

        else:
            # Если да, то сохраняем пользователя
            user_data[user_id]['authenticated'] = True
            await update.message.reply_text(f"Аутентификация прошла успешно! Вы вошли как {user_data[user_id]['role']} с логином {login}.")
            del user_data[user_id]['state'] # Сбрасываем состояние

    # Предоставляем функционал только для авторизированных пользователей
    if 'authenticated' in user_data[user_id]:
        # Получаем роль, для которой нужно вывести возможные команды
        role = user_data[user_id]['role']

        # Создаем удобную для пользователей клавиатуру
        keyboard = []
        for command in commands[role]:
            new_button = InlineKeyboardButton(command['text'],
                                              callback_data=command['callback_data'])
            keyboard.append([new_button])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Для вас доступны следующие команды:",
                                        reply_markup=reply_markup)


# Функции команд учителей
async def new_submissions(update, context):
    pass


async def class_grades(update, context):
    pass


# Функции команд учеников
async def new_tasks(update, context):
    pass


async def assessed_tasks(update, context):
    pass


async def grades(update, context):
    pass


# Переменная соответствия callback_data и названий обработчиков
match = {'new_submissions': new_submissions,
         'class_grades': class_grades,
         'new_tasks': new_tasks,
         'assessed_tasks': assessed_tasks,
         'grades': grades}


async def button_handler(update, context):
    """ Обрабатывает нажатия на inline-кнопки команд. """
    # Ожидаем действие пользователя
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data

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

    role = user_data[user_id]['role']

    # Вызываем соответствующую функцию на основе callback_data
    if role == 'учитель':
        if callback_data not in ['new_submissions', 'class_grades']:
            await query.message.reply_text("Неизвестная команда или нет доступа")

    elif role == 'ученик':
        if callback_data not in ['new_tasks', 'assessed_tasks', 'grades']:
            await query.message.reply_text("Неизвестная команда или нет доступа")

    else:
        await match[callback_data](update, context)


def main():
    """ Функция запуска бота. """
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Обработчики стартовых команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Обработчик нажатия всех кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Обработчики общения с пользователем
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, authentication))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, new_submissions))

    # Запуск приложения
    application.run_polling()


if __name__ == '__main__':
    main()
