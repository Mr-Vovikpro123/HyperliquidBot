from telebot import TeleBot
import os
import json
import threading
from time import sleep

from data_types import BotEvent
from logger_module import logger, log_path
from main_handler import BotsHandler



config_path_tg = os.path.join(os.path.dirname(__file__), "tg_config.json")
with open(config_path_tg) as f:
    config_tg = json.load(f)
TG_SECRET = config_tg["tg_secret"]
CHAT_ID = config_tg["chat_id"]


class TelegramNotifier:
    def __init__(self):
        self.bot = TeleBot(TG_SECRET)
        self.chat_id = CHAT_ID

    def notify(self, event: BotEvent) -> None:
        try:
            text = self._format(event)
            self.bot.send_message(self.chat_id, text)
        except Exception:
            logger.exception("Telegram send failed")

    def general_notification(self, message) -> None:
        try:
            self.bot.send_message(self.chat_id, message)
        except Exception:
            logger.exception("Telegram send failed")

    def _format(self, event: BotEvent) -> str:
        msg = f"[{event.level}] {event.symbol}\n{event.message}"
        if event.data:
            msg += f"\n\n{event.data}"
        return msg


class TelegramController:
    def __init__(self, bot_controller: BotsHandler):
        self.bot = TeleBot(TG_SECRET)
        self.controller: BotsHandler = bot_controller

        @self.bot.message_handler(func=lambda message: True)
        def echo_all(message):
            s = message.text.split(' ')
            command = s[0]

            if command == "add":
                self.controller.add_tracker(s[1])
            elif command == "remove":
                self.controller.remove_tracker(s[1])
            elif command == "terminate":
                self.controller.terminate_tracker(s[1])
            elif command == "exclude":
                self.controller.exclude_tracker(s[1])
            elif command == "ping":
                self.bot.reply_to(message, "Pong")
                return
            elif command == "log":
                with open(log_path, 'rb') as file:
                    self.bot.send_document(message.chat.id, file)
                return

            self.bot.reply_to(message, "OK")

        self.tg_thread = threading.Thread(target=self.run_telegram_polling, daemon=True)
        self.tg_thread.start()

    def run_telegram_polling(self):
        logger.info("Telegram polling thread started")

        while True:
            try:
                self.bot.polling(none_stop=True, interval=0, timeout=20)
            except Exception as e:
                logger.error(f"Telegram polling crashed: {e}", exc_info=True)
                sleep(5)
