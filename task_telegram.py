#!/usr/bin/env python
# pylint: disable=unused-argument

import sys
sys.path.append('/home/ubuntu/bobik')

import logging
import os
import re
import time
import yaml
from typing import Final
import asyncio
import nest_asyncio
import warnings ;

warnings.warn = lambda *args,**kwargs: None
from src.app import App
warnings.warn = lambda *args, **kwargs: None

from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    Updater,
    CallbackContext
)
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)


""" COMMANDS
info - current setup
clear - clear memory
agent - toggle agent mode
restart - restarts everything
start - loads tools keyboard
"""

yaml_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "task_telegram.yaml")
with open(yaml_file, 'r') as file:
    config = yaml.safe_load(file)

current_dir = os.path.dirname(os.path.abspath(__file__))

_bobik_apps = {}
def bobik(user: str) -> App:
    if user == "":
        raise Exception("Given empty user")

    if user in _bobik_apps:
        return _bobik_apps[user]

    def app_factory(config: str) -> App:
        return App(config_file=os.path.join(current_dir, config))

    _bobik_apps['helper'] = app_factory(config['bobik']['helper']['config'])
    for u in config['bobik']['users']:
        _bobik_apps[u['name']] = app_factory(u['config'])

    if user not in _bobik_apps:
        raise Exception(f"User {user} not configured")

    return _bobik_apps[user]


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

############################################
def extract_and_split(text, start_tag="<formatted_text>", end_tag="</formatted_text>", delimiter="----"):
    # Use regex for more robust tag matching
    pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    sections = re.findall(pattern, text, re.DOTALL)

    # Use list comprehension for splitting and flattening in one step
    split_sections = [
        subsection.strip()
        for section in sections
        for subsection in section.split(delimiter)
        if subsection.strip()
    ]

    return split_sections

def format_response_prompt(replacement_text) -> str:
    file = os.path.join(current_dir, "prompts", "telegram_markdown.md")
    if not os.path.exists(file):
        return [f"Error: File {file} not found"]

    with open(file, 'r') as f:
        content: str = f.read()
        question = content.replace("{{TEXT_TO_FORMAT}}", replacement_text)
        return question

async def handle_respone(user: str, question: str):
    try:
        response = await bobik(user).answer(questions=[question])
        if response == "":
            return ["Sorry, I broke. 😢"]

        format_prompt = format_response_prompt(response)
        response = await bobik('helper').answer(questions=["gpt " + format_prompt])
        print(response)
        answers = extract_and_split(text=response)

        return answers
    except KeyboardInterrupt:
        quit(1)
    except Exception as e:
        return [f"Error: {e}"]

async def send_typing_action(context, chat_id):
    while True:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        await asyncio.sleep(5)  # Telegram's typing action lasts 5 seconds


async def respond(answers: list, update: Update):
    for text in answers:
        try:
            await update.message.reply_html(text)
        except Exception as e:
            print("failed html reply err:", e)
            await update.message.reply_text(text)

async def handle_message_txt(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    print(f'User ({update.message.chat.id}) in {message_type}: "{text}"')

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

        answers = ["Sorry, I can't help you."]
        if update.message.from_user.username in ['Bearterror', 'andrejsstepanovs'] and message_type == "private":
            if update.message.reply_to_message:
                text += "\n\n<quoted_text>" + update.message.reply_to_message.text + "</quoted_text>"
            answers = await handle_respone(update.message.from_user.username, text)

    except Exception as e:
        answers = [f"Error: {e}"]

    await respond(answers, update)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_message_txt(update.message.text, update, context)

async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username
    tasks_in_row = 2

    options = []
    choices = []
    i = 0
    for name, commands in bobik(user).get_manager().config.settings.tasks.items():
        choices.append(name)
        if i >= tasks_in_row:
            i = 0
            options.append(choices)
            choices = []
            continue
        i += 1

    if len(choices) > 0:
        options.append(choices)

    reply_markup = ReplyKeyboardMarkup(
        options,
        input_field_placeholder=None,
        one_time_keyboard=False, # Requests clients to hide the keyboard as soon as it’s been used
        is_persistent=True,      # Requests clients to always show the keyboard when the regular keyboard is hidden
        resize_keyboard=True     # Requests clients to resize the keyboard vertically for optimal fit
    )

    await update.message.reply_text("✅ Tasks updated", reply_markup=reply_markup)


async def handle_image(update: Update, context: CallbackContext):
    photo = update.message.photo
    if photo:
        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        message = "summarize this image description"
        if update.message.caption:
            message = update.message.caption
    else:
        await update.message.reply_text(f"Not a image. I dont know how to process it yet.")
        return

    helper = bobik('helper')
    helper.get_manager().clear_memory()
    response = await helper.answer(questions=[f"gpt4o llm describe in detail this image {photo_file.file_path}"])

    prompt = f"{message}. Detailed image description: {response}"
    await handle_message_txt(prompt, update, context)


async def handle_voice(update: Update, context: CallbackContext):
    new_file = await context.bot.get_file(update.message.voice.file_id)
    AUDIO_FILE = await new_file.download_to_drive()
    print("Voice downloaded", AUDIO_FILE)

    try:
        deepgram = DeepgramClient(config['deepgram']['api_key'])
        with open(AUDIO_FILE, "rb") as file:
            buffer_data = file.read()

        payload: FileSource = {"buffer": buffer_data}
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
        )
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

        transcripts = ""
        for channel in response["results"]["channels"]:
            for alternative in channel["alternatives"]:
                transcripts += alternative["transcript"] + " "

        answers = await handle_respone(update.message.from_user.username, transcripts)
        await respond(answers, update)

    except Exception as e:
        print(f"Exception: {e}")

    os.remove(AUDIO_FILE)

async def toggle_agent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username
    bobik(user).get_manager().state.are_tools_enabled = not bobik(user).get_manager().state.are_tools_enabled
    answer = "Agent mode *OFF* 🌑🙅‍♂️"
    if bobik(user).get_manager().state.are_tools_enabled:
        answer = "Agent mode *ON* 💡🙆‍♂️"
    print("AGENT:", bobik(user).get_manager().state.are_tools_enabled)
    bobik(user).get_manager().reload_agent(force=True)
    await update.message.reply_text(answer)

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Restarting...")
    await update.message.reply_text("Try again in a few seconds")
    time.sleep(1)
    quit(1)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username
    is_agent = "disabled"
    if bobik(user).get_manager().state.are_tools_enabled:
        is_agent = "enabled"
    messages = [f"User: {user}\nActive model: {bobik(user).state.llm_model}\nAgent: {is_agent}"]

    models = []
    for model_name, model_config in bobik(user).settings.models.items():
        if not model_config.model:
            continue
        models.append(model_name)

    messages.append(f"Available models: {', '.join(models)}")
    for message in messages:
        await update.message.reply_text(message)

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username
    bobik(user).get_manager().clear_memory()
    await update.message.reply_text("✅ Memory cleared")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

def main() -> None:
    """Run the bot."""
    nest_asyncio.apply()

    print("Starting Bobik Bot...")
    app = Application.builder().token(config['telegram']['token']).build()

    # Commands
    app.add_handler(CommandHandler('clear', clear_command))
    app.add_handler(CommandHandler('info', info_command))
    app.add_handler(CommandHandler('restart', restart_command))
    app.add_handler(CommandHandler('agent', toggle_agent_command))
    app.add_handler(CommandHandler('start', task_command))
    app.add_handler(CommandHandler('task', task_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    # Errors
    app.add_error_handler(error)

    app.run_polling(poll_interval=3)


if __name__ == "__main__":
    main()
