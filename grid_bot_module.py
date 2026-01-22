import numpy as np
import queue
from queue import Queue
from time import sleep
from hyperliquid.utils.error import ClientError
from hyperliquid.utils.types import (
    UserEventsMsg,
)

from logger_module import logger
from data_types import BotEvent


def get_side(side):
    if side == "Sell":
        return False
    else:
        return True

class GridBot:
    def __init__(self, address, exchange, info_manager, notifier, raw, sz_decimals):
        self.info_manager = info_manager
        self.notifier = notifier
        self.exchange = exchange
        self.address = address
        self.symbol = raw["symbol"]
        self.deposit = raw["deposit"]
        self.order_distance = raw["order_distance"]
        self.profit_rate = raw["profit_rate"]
        self.leverage = raw["leverage"]
        self.order_count = raw["order_count"]
        self.martingale = raw["martingale"]
        self.deposit_fraction = raw["deposit_fraction"]
        self.side_bool = get_side(raw["side"])

        self.sz_decimals_symbol = sz_decimals[self.symbol]

        self.tp_id = 0
        self.start = True
        self.in_position_flag = False
        self.cmd_queue = Queue()

        self.order_ids = [0] * self.order_count
        self.order_prices = np.zeros(self.order_count)
        self.order_quantities = np.zeros(self.order_count)
        self.order_take_profits = np.zeros(self.order_count)
        self.order_average_prices = np.zeros(self.order_count)

        self.base_quantity = (self.deposit * self.deposit_fraction * np.power(self.martingale,
                                                                              np.arange((-self.order_count // 2) + 1, (
                                                                                          self.order_count // 2) + 1))) / self.order_count * self.leverage

    def main_cycle(self):
        while self.start:
            logger.info(f"[{self.symbol}] - Starting new grid cycle")
            self.calculate_grid(float(self.info_manager.info.all_mids().get(self.symbol)))

            self.place_order_0()
            self.place_tp_0()
            self.place_all_orders()

            self.in_position_flag = True
            while self.in_position_flag:
                try:
                    cmd, arg, arg1 = self.cmd_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if cmd == "UPDATE_TP":
                    #Signal from websocket triggers the update based on the last filled (even partially) order,
                    # but signal from data restore function only considers completely filled orders,
                    # so the takeprofit may shift back and forth in some cases
                    if arg != 0:
                        self.amend_tp_n(arg)

                elif cmd == "ORDER_FILL":
                    if arg != 0:
                        self.amend_tp_n(arg)
                    self.notifier.notify(
                        BotEvent(
                            symbol=self.symbol,
                            level="INFO",
                            message="Order filled",
                            data={"order": arg,
                                  "data": arg1}
                        )
                    )

                elif cmd == "TP_FILL":
                    if self.get_position_size() == 0.0:
                        self.in_position_flag = False
                        self.cancel_all_orders()
                        self.notifier.notify(
                            BotEvent(
                                symbol=self.symbol,
                                level="INFO",
                                message="TP filled",
                                data={"data": arg1}
                            )
                        )

                        logger.info(f"[{self.symbol}] - TakeProfit has been executed and the cycle is now over")
                        sleep(5)

                elif cmd == "NO_POS":
                    self.in_position_flag = False
                    self.cancel_all_orders()

                    logger.info(f"[{self.symbol}] - Data-restore function did not find any positions")
                    sleep(5)

    def on_user_events(self, user_events: UserEventsMsg) -> None:
        try:
            fills = user_events.get("data", {}).get("fills")
            if not fills:
                return

            for fill in fills:
                oid = fill.get("oid")

                if oid in self.order_ids:
                    idx = self.order_ids.index(oid)
                    self.cmd_queue.put(("ORDER_FILL", idx, fill))

                elif oid == self.tp_id:
                    self.cmd_queue.put(("TP_FILL", None, fill))

                elif fill.get("coin") == self.symbol:
                    logger.warning(f"[{self.symbol}] - Unexpected order has been filled!")

        except Exception as e:
            logger.error(f"[{self.symbol}] - User event handler error: {e}", exc_info=True)

    def round_px(self, px):
        max_decimals = 6
        if px > 100_000:  # Check if price is greater than 100k in which case we just need to round to an integer
            return round(px)
        else:  # If not we round px to 5 significant figures and max_decimals - szDecimals decimals
            return round(float(f"{px:.5g}"), max_decimals - self.sz_decimals_symbol)

    def round_sz(self, sz):
        # Round sz based on the sz_decimals map we created
        return round(sz, self.sz_decimals_symbol)

    def get_position_size(self) -> float:
        state = self.info_manager.info.user_state(self.address)
        for p in state.get("assetPositions", []):
            if p["position"]["coin"] == self.symbol:
                return abs(float(p["position"]["szi"]))
        return 0.0

    def sync_state_after_reconnect(self, open_orders, user_state):
        logger.info(f"[{self.symbol}] - State sync after WS reconnect")

        if self.in_position_flag:  # No need to restore data if the grid is not running
            current_pos = 0.0
            for p in user_state.get("assetPositions", []):
                if p["position"]["coin"] == self.symbol:
                    current_pos = abs(float(p["position"]["szi"]))
                    break

            logger.info(f"[{self.symbol}] - Current position: {current_pos}")
            if current_pos == 0.0:
                self.cmd_queue.put(("NO_POS", None, None))
                return

            k = 0
            for order in open_orders:
                if order["coin"] == self.symbol:
                    if order["oid"] in self.order_ids:
                        k += 1
            logger.info(f"[{self.symbol}] - Orders detected: {k}")
            self.cmd_queue.put(("UPDATE_TP", self.order_count - k - 1, None))

    def calculate_grid(self, price):
        if self.side_bool:
            price_factors = np.power(1 - self.order_distance, np.arange(0, self.order_count))
            self.order_prices = price * price_factors

            self.order_quantities = np.maximum(self.base_quantity / self.order_prices, 10 / price)
            self.order_average_prices = np.cumsum(self.order_prices * self.order_quantities) / np.cumsum(
                self.order_quantities)
            self.order_take_profits = self.order_average_prices * (1 + self.profit_rate)
        else:
            print("-")

    def place_order_0(self):
        try:
            order_result = self.exchange.market_open(
                name=self.symbol,
                is_buy=self.side_bool,
                sz=self.round_sz(self.order_quantities[0]),
            )
            logger.info(f"[{self.symbol}] - Placed order #0 as market, result: {order_result}")
            if order_result["status"] == "ok":
                status = order_result["response"]["data"]["statuses"][0]
                if "filled" in status:
                    self.order_ids[0] = status["filled"]["oid"]
        except ClientError as e:
            logger.error(f"[{self.symbol}] - Place market order failed #0: {e}", exc_info=True)

    def place_tp_0(self):
        try:
            order_result = self.exchange.order(
                name=self.symbol,
                is_buy=(not self.side_bool),
                sz=0,
                limit_px=self.round_px(self.order_take_profits[0]),
                order_type={"limit": {"tif": "Gtc"}},
                reduce_only=True
            )
            logger.info(f"[{self.symbol}] - Placed TakeProfit #0, result: {order_result}")
            if order_result["status"] == "ok":
                status = order_result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    self.tp_id = status["resting"]["oid"]
        except ClientError as e:
            logger.error(f"[{self.symbol}] - Place tp failed #0: {e}", exc_info=True)

    def amend_tp_n(self, n):
        try:
            order_result = self.exchange.modify_order(
                oid=self.tp_id,
                name=self.symbol,
                is_buy=(not self.side_bool),
                sz=0,
                limit_px=self.round_px(self.order_take_profits[n]),
                order_type={"limit": {"tif": "Gtc"}},
                reduce_only=True
            )
            logger.info(f"[{self.symbol}] - TakeProfit amended to the price #{n}, result: {order_result}")
            if order_result["status"] == "ok":
                status = order_result["response"]["data"]["statuses"][0]
                if "resting" in status:
                    self.tp_id = status["resting"]["oid"]
                elif "filled" in status:
                    self.cmd_queue.put(("TP_FILL", None))  # In case of immediate fill
        except ClientError as e:
            logger.error(f"[{self.symbol}] - Modify tp failed: {e}", exc_info=True)

    def place_all_orders(self):
        try:
            orders = []
            for i in range(1, self.order_count):
                orders.append({
                    "coin": self.symbol,
                    "is_buy": self.side_bool,
                    "sz": self.round_sz(self.order_quantities[i]),
                    "limit_px": self.round_px(self.order_prices[i]),
                    "order_type": {"limit": {"tif": "Gtc"}},
                    "reduce_only": False
                })
            order_result = self.exchange.bulk_orders(orders)
            logger.info(f"[{self.symbol}] - Placed all orders, result: {order_result}")
            if order_result["status"] == "ok":
                statuses = order_result["response"]["data"]["statuses"]
                k = 1
                for status in statuses:
                    if "resting" in status:
                        self.order_ids[k] = status["resting"]["oid"]
                    k += 1
        except ClientError as e:
            logger.error(f"[{self.symbol}] - Batch place failed: {e}", exc_info=True)

    def cancel_all_orders(self):
        open_orders = self.info_manager.info.open_orders(self.address)
        orders = []

        for open_order in open_orders:
            if open_order["coin"] == self.symbol:
                orders.append({"coin": open_order["coin"], "oid": open_order["oid"]})

        try:
            result = self.exchange.bulk_cancel(orders)
            logger.info(f"[{self.symbol}] - Cancelled all orders, result: {result}")
        except ClientError as e:
            logger.error(f"[{self.symbol}] - Failed to cancel: {e}", exc_info=True)

        self.clear_grid()

    def clear_grid(self):
        logger.info(f"[{self.symbol}] - Wiping the grid data")
        self.order_ids = [None] * self.order_count
        self.tp_id = 0