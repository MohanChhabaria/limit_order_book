from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Literal, Optional, Tuple
from sortedcontainers import SortedDict

OrderType = Literal[1, -1]

@dataclass
class OrderState:
    order_id: int
    order_type: OrderType
    price: float
    qty: int
    alive: bool = True
    version: int = 0

class OrderMatchingEngine:
    """
    In-memory order book
      - bids: SortedDict[price] -> deque(order_id)
      - asks: SortedDict[price] -> deque(order_id)
      - order_state_dict: order_id -> OrderState
      - bid_price_quantity_dict/ask_price_quantity_dict: price vs quantity for orders
    """

    def __init__(self) -> None:
        self.bids: SortedDict[float, Deque[int]] = SortedDict()
        self.asks: SortedDict[float, Deque[int]] = SortedDict()
        self.order_state_dict: Dict[int, OrderState] = {}
        self.bid_price_quantity_dict: Dict[float, int] = {}
        self.ask_price_quantity_dict: Dict[float, int] = {}
        self.last_seen_version_dict: Dict[int, int] = {}

        print("last seen version dict", self.last_seen_version_dict)


    def allow(self, order_id: int, version: int) -> bool:
        prev = self.last_seen_version_dict.get(order_id, 0)
        print("prev is ", prev)
        print("version is ", version)
        if version > prev:
            self.last_seen_version_dict[order_id] = version
            return True
        return False

    def place_order(self, order_id: int, order_type: OrderType, price: float, qty: int, version: int) -> List[dict]:
        print("entered place order function")
        if not self.allow(order_id, version):
            return []
        st = OrderState(order_id=order_id, order_type=order_type, price=price, qty=qty, alive=True, version=version)
        print("state is", st, "\n")
        self.order_state_dict[order_id] = st
        self._insert(st)

        return self._match_loop()

    def modify_order(
        self, order_id: int, updated_price: float, version: int
    ) -> List[dict]:
        if not self.allow(order_id, version):
            return []
        st = self.order_state_dict.get(order_id)
        if not st or not st.alive or st.qty <= 0:
            return []
        if st.price == updated_price:
            return []

        self._decrement_level_qty(st.order_type, st.price, st.qty)
        st.price = updated_price
        # Reinsert to new level
        self._insert(st)
        return self._match_loop()

    def cancel_order(self, *, order_id: int, version: int) -> None:
        if not self.allow(order_id, version):
            return
        st = self.order_state_dict.get(order_id)
        if not st or not st.alive or st.qty <= 0:
            return
        # Remove remaining qty from aggregates and mark dead (lazy removal from deque)
        self._decrement_level_qty(st.order_type, st.price, st.qty)
        st.qty = 0
        st.alive = False

    def top5_snapshot(self) -> dict:
        bids, asks = [], []

        # BIDS: highest → lowest
        for price in reversed(self.bids.keys()):
            if len(bids) >= 5:
                break
            total = self.bid_price_quantity_dict.get(price, 0)
            if total > 0:
                bids.append({"price": float(round(price, 2)), "quantity": int(total)})

        # ASKS: lowest → highest
        for price in self.asks.keys():
            if len(asks) >= 5:
                break
            total = self.ask_price_quantity_dict.get(price, 0)
            if total > 0:
                asks.append({"price": float(round(price, 2)), "quantity": int(total)})

        return {"bids": bids, "asks": asks}


    # ---------- Internal helpers ----------

    def _insert(self, st: OrderState) -> None:
        """Append order_id to the tail of its price level deque; bump level aggregate."""
        book = self.bids if st.order_type == 1 else self.asks
        level_qty = self.bid_price_quantity_dict if st.order_type == 1 else self.ask_price_quantity_dict

        dq = book.get(st.price)
        if dq is None:
            dq = deque()
            book[st.price] = dq
        dq.append(st.order_id)

        # Increase level aggregate by remaining qty
        level_qty[st.price] = level_qty.get(st.price, 0) + st.qty

    def _decrement_level_qty(self, order_type: OrderType, price: float, delta: int) -> None:
        """Decrease per-price aggregate; prune empty levels (aggregate only)."""
        level_qty = self.bid_price_quantity_dict if order_type == 1 else self.ask_price_quantity_dict
        book = self.bids if order_type == 1 else self.asks

        if delta <= 0:
            return
        new_val = level_qty.get(price, 0) - delta
        if new_val <= 0:
            level_qty.pop(price, None)
        else:
            level_qty[price] = new_val

        if new_val <= 0:
            self._remove_if_empty(order_type, price)

    def _remove_if_empty(self, order_type: OrderType, price: float) -> None:
        """Drop an empty price level deque (after lazy removals)."""
        book = self.bids if order_type == 1 else self.asks
        dq = book.get(price)
        if dq is None:
            return

        while dq and not self._is_order_live(dq):
            dq.popleft()
        if not dq:
            # Fully empty: remove the level
            book.pop(price, None)

    def _is_order_live(self, dq: Deque[int]) -> bool:
        """Peek head id and check if its order is alive and has qty > 0."""
        if not dq:
            return False
        head_id = dq[0]
        st = self.order_state_dict.get(head_id)
        return bool(st and st.alive and st.qty > 0)

    def _get_best_order_state(self, order_type: OrderType, price: float) -> Optional[OrderState]:
        """Pop until a live order is found at the head; returns its state or None."""
        book = self.bids if order_type == 1 else self.asks
        dq = book.get(price)
        if dq is None:
            return None
        while dq:
            oid = dq[0]
            st = self.order_state_dict.get(oid)
            if st and st.alive and st.qty > 0 and st.price == price:
                return st
            dq.popleft()
        book.pop(price, None)
        return None

    def _best_bid_price(self) -> Optional[float]:
        if not self.bids:
            return None
        # Last key in bids sorted dict
        return self.bids.peekitem(-1)[0]

    def _best_ask_price(self) -> Optional[float]:
        if not self.asks:
            return None
        # Last key in asks sorted dict
        return self.asks.peekitem(0)[0]

    # ---------- Matching logic ----------

    def _check_crossed(self) -> bool:
        best_bid = self._best_bid_price()
        best_ask = self._best_ask_price()
        if best_bid and best_ask and best_bid >=best_ask:
            return True
        return False

    def _match_loop(self) -> List[dict]:
        """
        While best bid >= best ask:
          - take head order at best bid and best ask (FIFO per price)
          - trade at resting order's price (ask price when buyer crosses; bid price when seller crosses)
        Returns list of trades: dict(price, qty, bid_order_id, ask_order_id).
        """
        trades: List[dict] = []
        while self._check_crossed():
            best_bid = self._best_bid_price()
            best_ask = self._best_ask_price()

            bid_state = self._get_best_order_state(1, best_bid)
            if bid_state is None:
                self._remove_if_empty(1, best_bid)
                continue
            ask_state = self._get_best_order_state(-1, best_ask)
            if ask_state is None:
                self._remove_if_empty(-1, best_ask)
                continue


            trade_price = best_ask

            trade_quantity = min(bid_state.qty, ask_state.qty)

            bid_state.qty -= trade_quantity
            ask_state.qty -= trade_quantity


            self._decrement_level_qty(1, best_bid, trade_quantity)
            self._decrement_level_qty(-1, best_ask, trade_quantity)

            # If an order is fully filled, mark it as completed
            if bid_state.qty == 0:
                bid_state.alive = False
                dq = self.bids.get(best_bid)
                if dq and dq[0] == bid_state.order_id:
                    dq.popleft()
                self._remove_if_empty(1, best_bid)

            if ask_state.qty == 0:
                ask_state.alive = False
                dq = self.asks.get(best_ask)
                if dq and dq and dq[0] == ask_state.order_id:
                    dq.popleft()
                self._remove_if_empty(-1, best_ask)
            else:
                pass

            trades.append({
                "price": trade_price,
                "qty": trade_quantity,
                "bid_order_id": bid_state.order_id,
                "ask_order_id": ask_state.order_id,
            })

        return trades