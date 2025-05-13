import asyncio
from admin_only import BOT_TOKEN
from database import authenticate_user

from telegram import (ReplyKeyboardMarkup,
                      InlineKeyboardButton,
                      InlineKeyboardMarkup)

from telegram.ext import (Application,
                          ConversationHandler,
                          MessageHandler,
                          CommandHandler,
                          ApplicationBuilder,
                          CallbackQueryHandler,
                          filters)


# Создаем глобальную переменную для хранения информации о пользователях
user_data = {}


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
        [InlineKeyboardButton("Ученик", callback_data='student')],
        [InlineKeyboardButton("Учитель", callback_data='teacher')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text('Вы ученик или учитель?', reply_markup=reply_markup)


async def start_button(update, context):
    """ Функция обработки выбора роли пользователя. """
    # Ожидаем действие пользователя
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data[user_id]['role'] = query.data  # Сохраняем роль

    await query.edit_message_text(text=f"Вы выбрали роль: {query.data}. Теперь войдите в аккаунт (если у вас нет аккаунта, зарегистрируйтесь на веб-платформе)")
    user_data[user_id]['state'] = 'waiting_for_login'  # Устанавливаем состояние "ожидает логин" для последующей аутентификации


async def start_conversation(update, context) -> None:
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
        if authenticate_user(login, password):
            # Если да, то сохраняем пользователя в переменной
            # При этом в целях безопасности мы нигде не сохраняем указанный пароль
            user_data[user_id]['authenticated'] = True
            await update.message.reply_text(f"Аутентификация прошла успешно! Вы вошли как {user_data[user_id]['role']} с логином {login}.")
            del user_data[user_id]['state'] # Сбрасываем состояние

            # Получаем роль, для которой нужно вывести возможные команды
            role = user_data[user_id]['role']

            if role == 'teacher':
                keyboard = [['/new_submissions', '/class_grades']]

            else:
                keyboard = [['/new_tasks', '/assessed_tasks'],
                            ['/grades']]

            reply_markup = ReplyKeyboardMarkup(keyboard)
            await update.message.reply_text("Для вас доступны следующие команды:", reply_markup=reply_markup)

        # Если пользователь не существует, то мы удаляем все полученные ранее данные и просим его пройти аутентификацию еще раз
        else:
            await update.message.reply_text("Неверный логин или пароль. Попробуйте еще раз")
            del user_data[user_id]['login'] # Сбрасываем данные пользователя
            user_data[user_id]['state'] = 'waiting_for_login'

    # Случай, когда бот не понимает запрос пользователя
    else:
        await update.message.reply_text("Начни с /start")


async def new_submissions(update, context):
    pass


async def class_grades(update, context):
    pass


async def new_tasks(update, context):
    pass


async def assessed_tasks(update, context):
    pass


async def grades(update, context):
    pass


def main():
    """ Функция запуска бота. """
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(start_button))  # Обрабатывает нажатия кнопок
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, start_conversation))

    # Удобное добавление обработчиков
    functions = [new_submissions, class_grades, new_tasks, assessed_tasks, grades]

    for function in functions:
        application.add_handler(CommandHandler(function.__name__, function))

    # Запуск приложения
    application.run_polling()


if __name__ == '__main__':
    main()
