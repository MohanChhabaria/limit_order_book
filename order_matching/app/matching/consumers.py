import asyncio, json
import time
from typing import Any, Dict
from redis.asyncio import Redis


from .engine import OrderMatchingEngine
from ..infra.redis import get_redis
from ..infra.settings import ORDERS_STREAM, ORDERS_GROUP, ORDERS_CONSUMER, TRADES_STREAM
from ..ws.manager import ws_manager

engine = OrderMatchingEngine()


def build_trade_event(trade: Dict) -> Dict:
    trade_id = f"{trade['bid_order_id']}-{trade['ask_order_id']}-{trade['qty']}"
    payload = {
        "trade_id": trade_id,
        "price": float(trade["price"]),
        "quantity": int(trade["qty"]),
        "bid_order_id": int(trade["bid_order_id"]),
        "ask_order_id": int(trade["ask_order_id"]),
    }
    return {
        "event_type": "TradeExecuted",
        "trade_id": trade_id,
        "payload": json.dumps(payload, separators=(",", ":")),
    }


async def _ensure_group(r: Redis):
    try:
        await r.xgroup_create(ORDERS_STREAM, ORDERS_GROUP, id="$", mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise


async def orders_consumer_loop():
    r = await get_redis()
    await _ensure_group(r)

    while True:
        response = await r.xreadgroup(
            groupname=ORDERS_GROUP,
            consumername=ORDERS_CONSUMER,
            streams={ORDERS_STREAM: ">"},
            count=128,
            block=1000,
        )
        if not response:
            continue

        for _stream, messages in response:
            acknowledged = False
            for msg_id, fields in messages:
                try:
                    event_type =int(fields["event_type"])
                    order_id = int(fields["order_id"])
                    version = int(fields["version"])
                    payload = fields.get("payload")
                    if isinstance(payload, str):
                        payload = json.loads(payload)

                    trades = []
                    if event_type == 1:
                        trades = engine.place_order(
                            order_id=order_id,
                            order_type=int(payload["order_type"]),
                            price=float(payload["price"]),
                            qty=int(payload["quantity"]),
                            version=version,
                        )
                        acknowledged = True
                    elif event_type == 2:
                        trades = engine.modify_order(
                            order_id=order_id,
                            updated_price=float(payload["price"]),
                            version=version,
                        )
                        acknowledged = True
                    elif event_type == 3:
                        engine.cancel_order(
                            order_id=order_id,
                            version=version,
                        )
                        acknowledged = True
                    else:
                        await r.xack(ORDERS_STREAM, ORDERS_GROUP, msg_id)
                        continue


                    for trade in trades:
                        await ws_manager.trades_event(trade)
                        trade_details = build_trade_event(trade)
                        await r.xadd(TRADES_STREAM, trade_details)


                except Exception as e:
                    print("orders_consumer error:", msg_id, e)

            if acknowledged:
                await r.xack(ORDERS_STREAM, ORDERS_GROUP, msg_id)