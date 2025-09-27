import json

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from order.enums import OrderType, OrderStatus
from order.model_mixins import CreatedAtModelMixin, LastUpdatedAtModelMixin
from order.utils import update_order, round_upto_two_decimal_places




class Order(CreatedAtModelMixin, LastUpdatedAtModelMixin):
    order_type = models.IntegerField(choices=OrderType.choices, default=OrderType.BUY)
    status = models.PositiveIntegerField(choices=OrderStatus.choices, default=OrderStatus.NEW)
    avg_order_price = models.FloatField(default=0.0)
    quantity = models.PositiveIntegerField(default=0)
    avg_trade_price = models.FloatField(null=True, blank=True)
    traded_quantity = models.PositiveIntegerField(null=True,blank=True)
    order_alive = models.BooleanField(default=True)
    version = models.IntegerField(default=1, null=False, blank=False)


@receiver(pre_save, sender=Order)
def order_pre_save(instance=None, **kwargs):
    order = None
    if instance.id:
        try:
            order = Order.objects.get(pk=instance.pk)
        except Order.DoesNotExist:
            pass
    else:
        if instance.status == OrderStatus.FILLED or instance.status == OrderStatus.CANCELED:
            instance.order_alive = False
        else:
            instance.order_alive = True

    instance.avg_order_price = round_upto_two_decimal_places(instance.avg_order_price)
    if instance.avg_trade_price:
        instance.avg_trade_price = round_upto_two_decimal_places(instance.avg_trade_price)
    instance.__old_instance = order



class Trade(CreatedAtModelMixin):
    trade_id = models.CharField(max_length=128, unique=True)
    buy_order = models.ForeignKey(Order, related_name='buy_trades', on_delete=models.CASCADE)
    sell_order = models.ForeignKey(Order, related_name='sell_trades', on_delete=models.CASCADE)
    avg_trade_price = models.FloatField(default=0.0)
    quantity = models.PositiveIntegerField()

    def clean(self):
        errors = {}
        if self.id:
            if self.buy_order.order_type != OrderType.BUY:
                errors.setdefault('buy_order', []).append("Buy order must be of type BUY")
            if self.sell_order.order_type != OrderType.SELL:
                errors.setdefault('sell_order', []).append("Sell order must be of type SELL")

            if self.quantity > self.buy_order.quantity or self.quantity > self.sell_order.quantity:
                errors.setdefault('quantity', []).append("Trade quantity cannot be greater than order quantity")

        if len(errors):
            raise ValidationError(errors)

@receiver(pre_save, sender=Trade)
def trade_pre_save(instance=None, **kwargs):
    trade = None
    if instance.id:
        try:
            trade = Trade.objects.get(pk=instance.pk)
        except Trade.DoesNotExist:
            pass

    if instance.avg_trade_price:
        instance.avg_trade_price = round_upto_two_decimal_places(instance.avg_trade_price)
    instance.__old_instance = trade

@receiver(post_save, sender=Trade)
def trade_post_save(instance=None, created=False, **kwargs):
    if created:
        buy_order = instance.buy_order
        sell_order = instance.sell_order
        trade_quantity = instance.quantity
        trade_price = instance.avg_trade_price
        update_order(trade_price, trade_quantity, buy_order)
        update_order(trade_price, trade_quantity, sell_order)




class EventType(models.IntegerChoices):
    ORDER_CREATED = 1, "Order Created"
    ORDER_UPDATED = 2, "Order Updated"
    ORDER_DELETED = 3, "Order Deleted"


def validate_json_string(value: str):
    try:
        json.loads(value)
    except Exception:
        raise ValidationError("payload_text must be valid JSON")


class Outbox(models.Model):
    event_type = models.CharField(max_length=64)
    order_id = models.BigIntegerField()
    version = models.PositiveIntegerField(choices=EventType.choices, null=False, blank=False)
    payload_text = models.TextField(validators=[validate_json_string])
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["published_at", "created_at"]),
            models.Index(fields=["order_id", "version"]),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.event_type} #{self.order_id} v{self.version}"
