import logging
import os
import subprocess
import openai
from dotenv import load_dotenv
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater
from database.database import *

# ✅ Cargar variables del entorno
load_dotenv("app/.env")  # solo necesario si estás probando localmente

# ✅ Configurar OpenAI
OPENAI_TOKEN = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_TOKEN
CHATGPT_MODEL = os.environ.get("CHATGPT_MODEL")

class DefaultConfig:
    PORT = int(os.environ.get("PORT", 5000))
    TELEGRAM_TOKEN = os.environ.get("API_TELEGRAM")
    MODE = os.environ.get("MODE", "polling")
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    @staticmethod
    def init_logging():
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            level=DefaultConfig.LOG_LEVEL,
        )

def help_command_handler(update, context):
    update.message.reply_text("Type /start to register to the service")

def start_command_handler(update, context):
    add_new_user(str(update.message.chat.id))
    start_text = (
        "Hi there, this bot allows you to query ChatGPT directly from Telegram, "
        "even with voice messages! 🤯\n\n"
        "Use /reset to clear the conversation history.\n\n"
        "Credits: @faviasono ✌🏻\nYou are ready to go 🚀"
    )
    update.message.reply_text(start_text)

def echo(update, context):
    telegram_id = str(update.message.chat.id)
    message = update.message.text
    answer = generate_response(message, telegram_id)
    update.message.reply_text(answer)

def transcribe_voice_message(voice_message: str) -> str:
    with open(voice_message, "rb") as audio_file:
        result = openai.Audio.transcribe("whisper-1", audio_file)
    return result["text"]

def handle_voice_message(update, context):
    voice = context.bot.get_file(update.message.voice.file_id)
    voice.download("/tmp/audio.oga")
    subprocess.run(
        ["ffmpeg", "-y", "-i", "/tmp/audio.oga", "/tmp/audio.mp3"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    text = transcribe_voice_message("/tmp/audio.mp3")
    telegram_id = str(update.message.chat.id)
    answer = generate_response(text, telegram_id)
    update.message.reply_text(answer)

def generate_response(question: str, telegram_id: str) -> str:
    row = retrieve_history(telegram_id)
    prompt = create_question_prompt(row, question)
    response = openai.ChatCompletion.create(
        model=CHATGPT_MODEL or "gpt-3.5-turbo",
        messages=prompt
    )
    answer = response["choices"][0]["message"]["content"]
    update_history_user(telegram_id, question, answer)
    return answer

def error(update, context):
    logging.warning('Update "%s"', update)
    logging.exception(context.error)

def reset(update, context):
    telegram_id = str(update.message.chat.id)
    reset_history_user(telegram_id)

def main():
    print("TOKEN leido:", DefaultConfig.TELEGRAM_TOKEN)  # debug
    updater = Updater(token=DefaultConfig.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handlers
    dp.add_handler(CommandHandler("help", help_command_handler))
    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(CommandHandler("reset", reset))
    dp.add_handler(MessageHandler(Filters.text, echo))
    dp.add_handler(MessageHandler(Filters.voice, handle_voice_message))
    dp.add_error_handler(error)

    # Start polling or webhook
    if DefaultConfig.MODE == "webhook":
        updater.start_webhook(
            listen="0.0.0.0",
            port=DefaultConfig.PORT,
            url_path=DefaultConfig.TELEGRAM_TOKEN,
            webhook_url=DefaultConfig.WEBHOOK_URL + DefaultConfig.TELEGRAM_TOKEN
        )
        logging.info(f"Start webhook mode on port {DefaultConfig.PORT}")
    else:
        updater.start_polling()
        logging.info("Start polling mode")

    updater.idle()

if __name__ == "__main__":
    DefaultConfig.init_logging()
    logging.info(f"PORT: {DefaultConfig.PORT}")
    main()
