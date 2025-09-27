import json
from django.conf import settings
from django.utils import timezone
from celery import shared_task
from redis import Redis
from order.models import Outbox

BATCH = 500

def _redis() -> Redis:
    return Redis.from_url(getattr(settings, "CELERY_BROKER_URL", "redis://127.0.0.1:6379/0"),decode_responses=True)

@shared_task(name="publish_outbox_batch")
def publish_outbox_batch():
    r = _redis()
    stream = getattr(settings, "ORDERS_STREAM", "orders_stream")

    rows = list(
        Outbox.objects
        .filter(published_at__isnull=True)
        .order_by("created_at")[:BATCH]
    )
    if not rows:
        return 0

    for row in rows:
        payload = json.loads(row.payload_text)
        r.xadd(
            stream,
            {
                "event_type": row.event_type,
                "order_id": str(row.order_id),
                "version": str(row.version),
                "payload": json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                "ts": timezone.now().isoformat(),
            },
            id="*",
        )

    Outbox.objects.filter(id__in=[x.id for x in rows]).update(published_at=timezone.now())
    return len(rows)