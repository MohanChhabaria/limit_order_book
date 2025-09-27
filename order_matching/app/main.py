from contextlib import asynccontextmanager

from fastapi import FastAPI

from .ws.manager import ws_manager
from .ws.routes import router as ws_router
from .infra.redis import get_redis, close_redis
from .matching.consumers import orders_consumer_loop, engine
from .api.health import router as health_router
from .api.order_book import  router as order_book_router
import asyncio


async def order_book_broadcast_loop():
    while True:
        await asyncio.sleep(1.0)
        snapshot = engine.top5_snapshot()
        await ws_manager.order_book_snapshot(snapshot)



@asynccontextmanager
async def lifespan(app: FastAPI):
    r = await get_redis()
    await r.ping()

    consume_orders = asyncio.create_task(orders_consumer_loop())
    broadcast_order_book = asyncio.create_task(order_book_broadcast_loop())

    try:
        yield
    finally:
        for task in (consume_orders, broadcast_order_book):
            task.cancel()
            try:
                await task
            except Exception:
                pass
        await close_redis()


app = FastAPI(title="Order Matching Service", lifespan=lifespan)
# app.include_router(health_router, prefix="/api")
app.include_router(ws_router)
app.include_router(order_book_router, prefix="/api")
