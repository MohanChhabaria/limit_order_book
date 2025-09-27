import json

from django.db import transaction
from django.utils import timezone
from django.views.generic import ListView
from rest_framework import status
from rest_framework.generics import RetrieveUpdateDestroyAPIView, CreateAPIView, ListAPIView

from order.models import Order, Trade
from order.serializers import OrderDetailSerializer, OrderMinimumSerializer, TradeDetailSerializer
from rest_framework.response import Response

from order.enums import OrderStatus, OrderType
from rest_framework.views import APIView

from order.utils import safe_convert_to_bool
from order.enums import OrderType

from algotest_api.publisher import publish_order_to_redis

from order.models import Outbox, EventType


class CreateOrderAPIView(APIView):
    @staticmethod
    def post(request, *args, **kwargs):
        data = request.data
        quantity = data.get('quantity')
        order_type = data.get('order_type')
        avg_order_price = data.get('avg_order_price')

        if not any([quantity, order_type, avg_order_price]):
            return Response({"success": False, "error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except Exception:
            return Response({"success": False, "error": "quantity must be a positive integer"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            order_type = int(order_type)
            if order_type not in OrderType.values:
                raise ValueError
        except Exception:
            return Response({"success": False, "error": "order_type must be -1 (sell) or 1 (buy)"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            avg_order_price = float(avg_order_price)
            if avg_order_price <= 0:
                raise ValueError
        except Exception:
            return Response({"success": False, "error": "avg_order_price must be a positive number (2 decimals)"},
                            status=status.HTTP_400_BAD_REQUEST)


        with transaction.atomic():
            order = Order.objects.create(
                quantity=quantity,
                order_type=order_type,
                avg_order_price=avg_order_price
            )

            payload = {
                "event": EventType.ORDER_CREATED,
                "order_id": order.id,
                "order_type": order_type,
                "price": order.avg_order_price,
                "quantity": order.quantity,
                "version": 1,
                "ts": timezone.now().isoformat(),
            }
            outbox = Outbox.objects.create(
                event_type=EventType.ORDER_CREATED,
                order_id=order.id,
                version=1,
                payload_text=json.dumps(payload, separators=(",", ":")),
            )

            transaction.on_commit(lambda: publish_order_to_redis(outbox.id))


        return Response(OrderMinimumSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Order.objects.filter(order_alive=True)
    serializer_class = OrderDetailSerializer
    lookup_url_kwarg = 'order_id'
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        order_id = self.kwargs[self.lookup_url_kwarg]
        updated_price = request.data.get("avg_order_price")
        if updated_price is None:
            return Response({"success": False, "error": "avg_order_price is required"},
                            status=status.HTTP_400_BAD_REQUEST)


        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if not order.order_alive or order.status in (OrderStatus.CANCELED, OrderStatus.FILLED):
                return Response({"success": False}, status=status.HTTP_200_OK)

            order.version += 1
            order.avg_order_price = updated_price
            order.save(update_fields=["version", "avg_order_price", "last_updated_at"])

            payload = {
                "event": EventType.ORDER_UPDATED,
                "order_id": order.id,
                "order_type" : order.order_type,
                "price": order.avg_order_price,
                "version": order.version,
                "ts": timezone.now().isoformat()
            }
            outbox = Outbox.objects.create(
                event_type=EventType.ORDER_UPDATED,
                order_id=order.id,
                version=order.version,
                payload_text=json.dumps(payload, separators=(",", ":")),
            )
            transaction.on_commit(lambda: publish_order_to_redis(outbox.id))

        return Response({"success": True}, status=status.HTTP_200_OK)


    def destroy(self, request, *args, **kwargs):
        order_id = self.kwargs[self.lookup_url_kwarg]
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if not order.order_alive or order.status == OrderStatus.CANCELED:
                return Response({"success": False}, status=status.HTTP_200_OK)

            order.version += 1
            order.order_alive = False
            order.status = OrderStatus.CANCELED
            order.save(update_fields=["version", "order_alive", "status", "last_updated_at"])

            payload = {
                "event": EventType.ORDER_DELETED,
                "order_id": order.id,
                "version": order.version,
                "order_type" : order.order_type,
                "ts": timezone.now().isoformat()
            }
            outbox = Outbox.objects.create(
                event_type=EventType.ORDER_DELETED,
                order_id=order.id,
                version=order.version,
                payload_text=json.dumps(payload, separators=(",", ":")),
            )
            transaction.on_commit(lambda: publish_order_to_redis(outbox.id))

        return Response({"success": True}, status=status.HTTP_200_OK)


class GetAllOrdersView(ListAPIView):
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        orders = Order.objects.all()
        alive = safe_convert_to_bool(self.request.query_params.get('alive', False))
        if alive:
            orders = orders.filter(order_alive=True)
        return orders


class GetAllTradesView(ListAPIView):
    serializer_class = TradeDetailSerializer
    queryset = Trade.objects.all()