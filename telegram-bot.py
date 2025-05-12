import asyncio
from admin_only import BOT_TOKEN
from telegram.ext import (Application,
                          ConversationHandler,
                          MessageHandler,
                          CommandHandler,
                          )


async def start(update, context):
    user = update.effective_user
    await update.message.reply_html(
        rf"Здравствуй, {user.mention_html()}! Ты являешься учеником или учителем?",
    )


async def help_command(update, context):
    await update.message.reply_text("Зарегистрируйся в свой аккаунт, чтобы получить доступ к полезным функциям!")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.run_polling()


if __name__ == '__main__':
    main()
