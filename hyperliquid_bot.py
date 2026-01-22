from time import sleep

from logger_module import logger
from main_handler import BotsHandler
from telegram import TelegramController, TelegramNotifier


def main():
    logger.info("Starting the script")

    bot_handler = BotsHandler(TelegramNotifier())
    TelegramController(bot_handler)

    bot_handler.notifier.general_notification(
        "The script has been started. If it was not initiated by you, consider this message as an error signal.")
    while True:
        sleep(43200)


if __name__ == '__main__':
    main()
