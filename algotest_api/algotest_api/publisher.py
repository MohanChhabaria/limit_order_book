import json
from django.conf import settings
from django.utils import timezone
from redis import Redis

from order.models import Outbox, Trade



def _get_redis() -> Redis:
    url = getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
    return Redis.from_url(url, decode_responses=True)


def publish_order_to_redis(outbox_id: int) -> bool:
    try:
        outbox = Outbox.objects.get(id=outbox_id)
    except Outbox.DoesNotExist:
        return True

    if outbox.published_at:
        return True

    stream = getattr(settings, "ORDERS_STREAM", "orders_stream")

    try:
        r = _get_redis()
        payload = json.loads(outbox.payload_text)

        r.xadd(
            stream,
            {
                "event_type": outbox.event_type,
                "order_id": str(outbox.order_id),
                "version": str(outbox.version),
                "payload": json.dumps(payload, separators=(",", ":")),
                "ts": timezone.now().isoformat()
            },
            id="*",
        )
        Outbox.objects.filter(id=outbox.id, published_at__isnull=True).update(published_at=timezone.now())
        return True
    except Exception:
        return False
