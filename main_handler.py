import threading
import yaml
from time import sleep
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.utils.types import (
    UserEventsMsg,
)

from logger_module import logger
from setup_api import setup
from grid_bot_module import GridBot

net = constants.MAINNET_API_URL

class BotsHandler:
    def __init__(self, notifier):
        logger.info("Initializing bot handler")

        self.trackers = []
        self.symbol_list = []
        self.threads = []

        self.address, self.exchange = setup(net)
        self.notifier = notifier

        self.info_manager = InfoManager(
            net,
            self.address,
            self.distribute_user_events,
            self.restore_data
        )
        self.info_manager.start()

        #Getting position size precision data
        self.sz_decimals = {}
        meta = self.info_manager.info.meta()
        for asset_info in meta["universe"]:
            self.sz_decimals[asset_info["name"]] = asset_info["szDecimals"]



    def add_new_tracker(self, symbol):
        with open(f'configs/{symbol}.yaml', 'r') as file:
            config = yaml.safe_load(file)
        tracker = GridBot(self.address, self.exchange, self.info_manager, self.notifier, config.get("bot_params"), self.sz_decimals)
        sleep(1)
        thr = threading.Thread(target=tracker.main_cycle)
        thr.start()
        self.threads.append(thr)
        self.trackers.append(tracker)

    def add_tracker(self, symbol):
        if symbol not in self.symbol_list:
            logger.info(f"Adding a new bot: {symbol}")
            if symbol not in self.symbol_list:
                logger.info("Creating new tracker")
                self.symbol_list.append(symbol)
                self.add_new_tracker(symbol)
            else:
                tracker_idx = self.symbol_list.index(symbol)
                tracker = self.trackers[tracker_idx]

                if self.threads[tracker_idx].is_alive():
                    logger.info("Re-enabling active bot")
                    tracker.start = True
                else:
                    logger.info("Reviving existing bot")
                    tracker.start = True
                    thr = threading.Thread(target=tracker.main_cycle)
                    thr.start()
                    self.threads[tracker_idx] = thr
        else:
            logger.warning(f"Can't add tracker that already exists: {symbol}")

    def remove_tracker(self, symbol):
        logger.info(f"Removing the bot: {symbol}")
        tracker = self.trackers[self.symbol_list.index(symbol)]
        tracker.start = False

    def terminate_tracker(self, symbol):
        logger.info(f"Terminating the bot: {symbol}")
        tracker = self.trackers[self.symbol_list.index(symbol)]
        tracker.start = False
        tracker.cancel_all_orders()

    def exclude_tracker(self, symbol):
        logger.info(f"Excluding the bot: {symbol}")
        idx = self.symbol_list.index(symbol)
        self.trackers.pop(idx)
        self.threads.pop(idx)
        self.symbol_list.pop(idx)

    def distribute_user_events(self, user_events: UserEventsMsg):
        logger.info(f"New user event: {user_events}")
        for tracker in self.trackers:
            tracker.on_user_events(user_events)

    def restore_data(self):
        logger.info("WS reconnected - performing state synchronization for all bots")

        try:
            # Receiving order data and position data
            open_orders = self.info_manager.info.open_orders(self.address)
            user_state = self.info_manager.info.user_state(self.address)

            for tracker in self.trackers:
                tracker.sync_state_after_reconnect(open_orders, user_state)

        except Exception as e:
            logger.error(f"State sync after reconnect failed: {e}", exc_info=True)




class InfoManager:
    def __init__(self, base_url, address, on_user_events_callback, on_reconnect_callback):
        self.base_url = base_url
        self.address = address
        self.on_user_events = on_user_events_callback  # function for user event routing
        self.on_reconnect_callback = on_reconnect_callback  # function to call when connection is restored
        self.info = None
        self.lock = threading.Lock()
        self.subscription = {"type": "userEvents", "user": self.address}
        self.first_connection = True

    def start(self):
        logger.info("Starting info manager")
        self._connect()
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _connect(self):
        try:
            logger.info("Connecting to Hyperliquid WS...")
            self.info = Info(self.base_url)
            logger.info("Subscribing on user events stream")
            self.info.subscribe(self.subscription, self.on_user_events)

            if self.first_connection:  #Prevents calling synchronisation function on setup
                self.first_connection = False
            else:
                try:
                    self.on_reconnect_callback()
                except Exception as e:
                    logger.error(f"Reconnect callback failed: {e}", exc_info=True)

            logger.warning("WS connected and subscribed")
        except Exception as e:
            logger.error(f"Failed to connect WS: {e}", exc_info=True)
            self.info = None

    def _watchdog(self):
        while True:
            sleep(8)
            with self.lock:
                if (self.info is None or
                        self.info.ws_manager is None or
                        not self.info.ws_manager.ws.keep_running):
                    logger.warning("WebSocket appears dead, conducting full reconnect")
                    self._connect()


