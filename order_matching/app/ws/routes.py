# app/ws/routes.py
from fastapi import APIRouter, WebSocket

from app.ws.manager import ws_manager

router = APIRouter()

@router.websocket("/ws/trades")
async def trades_ws(ws: WebSocket):
    await ws_manager.connect(ws, "trades")
    try:
        while True:
            # to make sure tht the connection is alive
            await ws.receive_text()
    except Exception:
        pass
    finally:
        ws_manager.disconnect(ws, "trades")

@router.websocket("/ws/order_book")
async def book_ws(ws: WebSocket):
    await ws_manager.connect(ws, "order_book")
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        ws_manager.disconnect(ws, "order_book")
