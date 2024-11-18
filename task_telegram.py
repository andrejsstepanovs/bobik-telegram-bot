#!/usr/bin/env python
# pylint: disable=unused-argument

import sys
sys.path.append('/home/ubuntu/bobik')

import logging
import os
import time
import yaml
import traceback
from typing import Final, List
import asyncio
import nest_asyncio
import warnings
import json
warnings.warn = lambda *args,**kwargs: None
from src.app import App
warnings.warn = lambda *args, **kwargs: None
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Update
from utils import extract_and_split, format_response_prompt, get_entries_to_execute
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    Updater,
    CallbackContext,
    JobQueue
)
from datetime import time, timezone
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)

class TelegramBot:
    def __init__(self):
        self.config = self.load_config()
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self._bobik_apps = {}
        self.CONFIGURED_USERNAMES = self.get_configured_usernames()
        self.setup_logging()
        self.jobs = {}

    def load_config(self):
        yaml_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "task_telegram.yaml")
        with open(yaml_file, "r") as file:
            return yaml.safe_load(file)

    def setup_logging(self):
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        self.logger = logging.getLogger(__name__)

    def bobik(self, user: str) -> App:
        if user == "":
            raise Exception("Given empty user")

        if user in self._bobik_apps:
            return self._bobik_apps[user]

        def app_factory(config: str) -> App:
            app = App(config_file=os.path.join(self.current_dir, config))
            app.state.is_quiet = True
            return app

        self._bobik_apps["helper"] = app_factory(self.config["bobik"]["helper"]["config"])
        for u in self.config["bobik"]["users"]:
            self._bobik_apps[u["name"]] = app_factory(u["config"])

        if user not in self._bobik_apps:
            raise Exception(f"User {user} not configured")

        return self._bobik_apps[user]

    def get_configured_usernames(self) -> List[dict]:
        return [{"name": u["name"], "proactive": u.get("proactive", False)} for u in self.config["bobik"]["users"]]

    async def handle_response(self, user: str, question: str):
        try:
            response = await self.bobik(user).answer(questions=[question])
            if response == "":
                return ["Sorry, I broke. 😢"]

            format_prompt = format_response_prompt(response, self.current_dir)
            response = await self.bobik("helper").answer(questions=["tiny " + format_prompt])
            print(response)
            answers = extract_and_split(text=response)

            return answers
        except KeyboardInterrupt:
            quit(1)
        except Exception as e:
            return [f"Error: {e}"]

    async def send_typing_action(self, context, chat_id):
        while True:
            await context.bot.send_chat_action(chat_id=chat_id, action='typing')
            await asyncio.sleep(5)

    async def respond(self, answers: list, update: Update):
        for text in answers:
            try:
                await update.message.reply_html(text)
            except Exception as e:
                print("failed html reply err:", e)
                await update.message.reply_text(text)

    async def handle_text_message(self, text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_type: str = update.message.chat.type
        print(f"User ({update.message.chat.id}) in {message_type}: \"{text}\"")

        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            answers = ["Sorry, I can't help you."]
            if update.message.from_user.username in [user["name"] for user in self.CONFIGURED_USERNAMES] and message_type == "private":
                if update.message.reply_to_message:
                    text += "\n\n<quoted_text>" + update.message.reply_to_message.text + "</quoted_text>"
                answers = await self.handle_response(update.message.from_user.username, text)

        except Exception as e:
            answers = [f"Error: {e}"]

        await self.respond(answers, update)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.handle_text_message(update.message.text, update, context)

    async def proactive_message(self, context: ContextTypes.DEFAULT_TYPE):
        username = context.job.data.get('user', 'there')
        try:
            config = False
            for a in self.config["bobik"]["users"]:
                if a["name"] == username:
                    config = a
            if config and not config['proactive']:
                return

            print("Using proactive_file:", config['proactive_file'])
            with open(config['proactive_file'], "r") as file:
                cron_config = file.read()
            cron_dict = json.loads(cron_config)

            user_timezone = self.bobik(username).settings.user.timezone
            entries = get_entries_to_execute(cron_dict, user_timezone)
            if len(entries) == 0:
                return
            prompts = []
            for entry in entries:
                print(f"Found and executing proactive prompt:", entry["prompt"])
                prompts.append(f"Proactive schedule: {entry['schedule']}. Topic: {entry['topic']} and Prompt: {entry['prompt']}")
            text = "\n".join(prompts)
            prompt = f"""You are an AI assistant tasked with creating proactive messages for users. These messages are not responses to direct questions, but rather unprompted information or suggestions that users will receive spontaneously. Your goal is to craft these messages in a way that feels natural, helpful, and engaging.

                        You will be given a topic for the proactive message. Here is the topic:

                        <proactive_topic>
                        {text}
                        </proactive_topic>

                        Based on this topic, formulate a proactive message that a user might find interesting or useful. Remember, the user has not triggered this via direct question for this information, so your message should be phrased as an unsolicited but welcome piece of information.

                        Follow these guidelines when crafting your message:

                        1. Start with a friendly, attention-grabbing opening that introduces the topic naturally.
                        2. Be concise but informative.
                        3. Include a brief explanation of why this information might be relevant or useful to the user.
                        4. End with a soft call-to-action or a question that encourages engagement, but don't be pushy.
                        5. Ensure the message feels spontaneous and not like a response to a query.
                        6. Don't ask user for any follow up questions.
                        7. Answer with single word "Nothing" (without quotes), if you have nothing reasonably important to say.

                        Remember, you're not responding to a user's question, but rather initiating a conversation on this topic. Frame your message accordingly.
                        Answer with the message that will be delivered to the user so no yapping, answer with only what needs to be sent to user.\n"""

            prompt_message = []
            for line in prompt.split("\n"):
                prompt_message.append(line.lstrip())

            chat_id = context.job.chat_id
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            answers = await self.handle_response(username, "\n".join(prompt_message))
            for answer in answers:
                if answer != "Nothing":
                    await context.bot.send_message(chat_id=chat_id, text=answer, parse_mode="HTML")
        except Exception as e:
            self.logger.error(f"Failed to send proactive message: {str(e)}")
            traceback.print_exc()

    async def task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.message.from_user.username
        tasks_in_row = 2

        options = []
        choices = []
        i = 0
        for name, commands in self.bobik(username).get_manager().config.settings.tasks.items():
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
            one_time_keyboard=False,
            is_persistent=True,
            resize_keyboard=True
        )

        await update.message.reply_text("✅ Tasks updated", reply_markup=reply_markup)

        for user in self.CONFIGURED_USERNAMES:
            if user["name"] == username and user["proactive"]:
                if username not in self.jobs:
                    self.jobs[username] = context.job_queue.run_repeating(self.proactive_message, interval=60, first=10, chat_id=update.message.chat_id, data={'user': username})
                    # self.jobs[username].enabled = False  # Temporarily disable this job
                    await update.message.reply_text("✅ Proactive job started")
                else:
                    await update.message.reply_text("✅ Proactive job already running")
            else:
                self.logger.info(f"Proactive messages are disabled for {user['name']}")

    async def handle_image(self, update: Update, context: CallbackContext):
        photo = update.message.photo
        if photo:
            photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
            message = "summarize this image description"
            if update.message.caption:
                message = update.message.caption
        else:
            await update.message.reply_text(f"Not a image. I dont know how to process it yet.")
            return

        helper = self.bobik('helper')
        helper.get_manager().clear_memory()
        response = await helper.answer(questions=[f"gpt4o llm describe in detail this image {photo_file.file_path}"])

        prompt = f"{message}. Detailed image description: {response}"
        await self.handle_text_message(prompt, update, context)

    async def handle_voice(self, update: Update, context: CallbackContext):
        new_file = await context.bot.get_file(update.message.voice.file_id)
        AUDIO_FILE = await new_file.download_to_drive()
        print("Voice downloaded", AUDIO_FILE)

        try:
            deepgram = DeepgramClient(self.config['deepgram']['api_key'])
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

            answers = await self.handle_response(update.message.from_user.username, transcripts)
            await self.respond(answers, update)

        except Exception as e:
            print(f"Exception: {e}")

        os.remove(AUDIO_FILE)

    async def toggle_agent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.message.from_user.username
        self.bobik(user).get_manager().state.are_tools_enabled = not self.bobik(user).get_manager().state.are_tools_enabled
        answer = "Agent mode *OFF* 🌑🙅‍♂️"
        if self.bobik(user).get_manager().state.are_tools_enabled:
            answer = "Agent mode *ON* 💡🙆‍♂️"
        print("AGENT:", self.bobik(user).get_manager().state.are_tools_enabled)
        self.bobik(user).get_manager().reload_agent(force=True)
        await update.message.reply_text(answer)

    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Restarting...")
        await update.message.reply_text("Try again in a few seconds")
        time.sleep(1)
        quit(1)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.message.from_user.username
        is_agent = "disabled"
        if self.bobik(user).get_manager().state.are_tools_enabled:
            is_agent = "enabled"
        messages = [f"User: {user}\nActive model: {self.bobik(user).state.llm_model}\nAgent: {is_agent}"]

        models = []
        for model_name, model_config in self.bobik(user).settings.models.items():
            if not model_config.model:
                continue
            models.append(model_name)

        messages.append(f"Available models: {', '.join(models)}")
        for message in messages:
            await update.message.reply_text(message)

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.message.from_user.username
        self.bobik(user).get_manager().clear_memory()
        await update.message.reply_text("✅ Memory cleared")

    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(f"Update {update} caused error {context.error}")

    async def get_user_id(self, username):
        try:
            chat = await self.application.bot.get_chat(f"@{username}")
            return chat.id
        except Exception as e:
            self.logger.error(f"Failed to get user ID for {username}: {str(e)}")
            return None

    def run(self):
        """Run the bot."""
        nest_asyncio.apply()

        print("Starting Bobik Bot...")
        self.application = Application.builder().token(self.config['telegram']['token']).build()

        # Commands
        self.application.add_handler(CommandHandler('clear', self.clear_command))
        self.application.add_handler(CommandHandler('info', self.info_command))
        self.application.add_handler(CommandHandler('restart', self.restart_command))
        self.application.add_handler(CommandHandler('agent', self.toggle_agent_command))
        self.application.add_handler(CommandHandler('start', self.task_command))
        self.application.add_handler(CommandHandler('task', self.task_command))

        # Messages
        self.application.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_image))

        # Errors
        self.application.add_error_handler(self.error)

        self.application.run_polling(poll_interval=3)

def main():
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    main()

""" COMMANDS
start - loads tools keyboard and starts proactive messages
info - current setup
clear - clear memory
agent - toggle agent mode
restart - restarts everything
"""
