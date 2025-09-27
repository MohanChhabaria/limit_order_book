from typing import Set, Iterable
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self) -> None:
        self.trade_websockets: Set[WebSocket] = set()
        self.order_book_websockets: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket, kind: str) -> None:
        await ws.accept()
        (self.trade_websockets if kind == "trades" else self.order_book_websockets).add(ws)

    def disconnect(self, ws: WebSocket, kind: str) -> None:
        (self.trade_websockets if kind == "trades" else self.order_book_websockets).discard(ws)


    async def _broadcast(self, clients: Iterable[WebSocket], payload) -> None:
        dead = []
        for ws in list(clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            try:
                await ws.close()
            except Exception:
                pass
            clients.discard(ws)

    async def trades_event(self, trade: dict) -> None:
        if self.trade_websockets:
            await self._broadcast(self.trade_websockets, {"type": "trade", **trade})

    async def order_book_snapshot(self, snapshot: dict) -> None:
        if self.order_book_websockets:
            await self._broadcast(self.order_book_websockets, {"type": "order_book", **snapshot})



ws_manager = WebSocketManager()
