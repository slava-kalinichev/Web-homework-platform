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
    # Получаем роль, для которой нужно вывести возможные команды
    role = user_data[user_id]['role']

    # Создаем удобную для пользователей клавиатуру
    keyboard = []
    for command in commands[role]:
        new_button = InlineKeyboardButton(command['text'],
                                          callback_data=command['callback_data'])
        keyboard.append([new_button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


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
    """ Функция обработки сообщения пользователя в зависимости от текущего состояния."""

    # Данная функция обрабатывает все сообщения пользователя,
    # которые используются как части диалогов для выполнения других функций
    # посредством установки состояния 'state', после чего введенное пользователем сообщение
    # считывается как необходимое для функции, указанной в том самом состоянии

    user_id = update.effective_user.id
    text = update.message.text

    # Проверяем, зарегистрирован ли идентификатор пользователя в боте
    if user_id not in user_data:
        await update.message.reply_text("Пожалуйста, начните с команды /start.")
        return

    # Проверяем наличие состояния
    if 'state' not in user_data[user_id]:
        await update.message.reply_text("Я не понимаю такой команды. Список доступных команд можно посмотреть с помощью команды /help")
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

            await update.message.reply_text(f"Для вас доступны следующие команды:",
                                            reply_markup=create_command_keyboard(user_id))

    elif user_data[user_id]['state'] == 'new_submissions':
        student_name = text
        reply_data = get_new_submissions(student_name)

        if reply_data is False:
            await update.message.reply_text("Такого ученика не существует")

        elif not reply_data:
            await update.message.reply_text(f"У ученика {student_name} проверены все сданные задания")

        else:
            await update.message.reply_textf(f"{student_name} имеет {len(reply_data)} непроверенных заданий: \n{'\n'.join(reply_data)}")

        del user_data[user_id]['state']

    elif user_data[user_id]['state'] == 'class_grades':
        class_name = text
        reply_data = get_class_grades(class_name)

        if reply_data is False:
            await update.message.reply_text("Такого класса не существует")

        elif not reply_data:
            await update.message.reply_text(f"У {class_name} еще нет оценок")

        else:
            await update.message.reply_text(f"Статистика {class_name}: \n{'\n'.join(reply_data)}")

        del user_data[user_id]['state']


# Функции команд учителей
async def new_submissions(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверка на соответствие роли
    if user_data[user_id]['role'] != 'учитель':
        await query.message.reply_text("Извините, данная команда доступна только учителям")

    # Устанавливаем состояние
    user_data[user_id]['state'] = 'new_submissions'
    await query.message.reply_text("Пожалуйста, введите имя ученика:")


async def class_grades(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверка на соответствие роли
    if user_data[user_id]['role'] != 'учитель':
        await query.message.reply_text("Извините, данная команда доступна только учителям")

    # Устанавливаем состояние
    user_data[user_id]['state'] = 'class_grades'
    await query.message.reply_text("Пожалуйста, введите названия класса:")


# Функции команд учеников
async def new_tasks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверка на соответствие роли
    if user_data[user_id]['role'] != 'ученик':
        await query.message.reply_text("Извините, данная команда доступна только ученикам")

    reply_data = get_new_tasks(user_data[user_id]['login'])

    if not reply_data:
        await query.message.reply_text("У вас нет новых заданий")

    else:
        await query.message.reply_text(f"У вас {len(reply_data)} невыполненных заданий: \n{'\n'.join(reply_data)}")


async def assessed_tasks(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверка на соответствие роли
    if user_data[user_id]['role'] != 'ученик':
        await query.message.reply_text("Извините, данная команда доступна только ученикам")

    reply_data = get_assessed_tasks(user_data[user_id]['login'])

    if not reply_data:
        await query.message.reply_text("Оцененных заданий нет")

    else:
        await query.message.reply_text(f"У вас оценено {len(reply_data)} заданий: \n{'\n'.join(reply_data)}")


async def grades(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверка на соответствие роли
    if user_data[user_id]['role'] != 'ученик':
        await query.message.reply_text("Извините, данная команда доступна только ученикам")

    reply_data = get_grades(user_data[user_id]['login'])

    if not reply_data:
        await query.message.reply_text("У вас нет оценок")

    else:
        await query.message.reply_text(f"За все время вы получили {len(reply_data)} оценок: \n"
                                        f"{'\n'.join(f'{task} - {grade}' for task, grade in reply_data.items())}")


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

    # Вызываем соответствующую функцию на основе callback_data
    if callback_data in match:
        await match[callback_data](update, context)

    else:
        await query.message.reply_text("Неизвестная команда.")


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
