
import asyncio
import json
import traceback

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from redis.asyncio import Redis
from redis.exceptions import ResponseError


from order.models import Trade



def _dec(v):
    return v.decode() if isinstance(v, (bytes, bytearray)) else v

def _normalize(fields: dict) -> dict:
    return { _dec(k): _dec(v) for k, v in fields.items() }

async def _ensure_group(r: Redis, stream: str, group: str, start_id: str = "$") -> None:
    try:
        await r.xgroup_create(stream, group, id=start_id, mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise

def _process_trade(data: dict) -> None:
    with transaction.atomic():
        Trade.objects.get_or_create(
            trade_id=data["trade_id"],
            defaults={
                "avg_trade_price": float(data["price"]),
                "quantity": int(data["quantity"]),
                "buy_order_id": int(data["bid_order_id"]),
                "sell_order_id": int(data["ask_order_id"]),
            },
        )



class Command(BaseCommand):

    def handle(self, *args, **options):
        asyncio.run(self._run())

    async def _run(self):
        stream   = getattr(settings, "TRADES_STREAM",   "trades_stream")
        group    = getattr(settings, "TRADES_GROUP",    "trade_fetcher")
        consumer = getattr(settings, "TRADES_CONSUMER", "trade_fetcher1")
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")

        r = Redis.from_url(redis_url)
        await _ensure_group(r, stream, group, start_id="$")

        self.stdout.write(self.style.SUCCESS("Trades consumer started."))

        try:
            while True:
                try:
                    response = await r.xreadgroup(
                        groupname=group,
                        consumername=consumer,
                        streams={stream: ">"},
                        count=128,
                        block=1000,
                    )
                except ResponseError as e:
                    if "NOGROUP" in str(e):
                        await _ensure_group(r, stream, group, start_id="$")
                        continue
                    raise

                if not response:
                    continue

                for _stream, messages in response:
                    for msg_id, fields in messages:
                        acknowledged = False
                        try:
                            fields = _normalize(fields)
                            evt_type = fields.get("event_type")
                            payload_raw = fields.get("payload")

                            if evt_type != "TradeExecuted":
                                acknowledged = True
                            else:
                                data = json.loads(payload_raw)
                                await sync_to_async(_process_trade, thread_sensitive=True)(data)
                                acknowledged = True

                        except Exception as exc:
                            self.stderr.write(f"[consume_trades] ERROR {msg_id}: {exc}")
                            self.stderr.write(traceback.format_exc())

                        if acknowledged:
                            await r.xack(stream, group, msg_id)
        finally:
            await r.aclose()
