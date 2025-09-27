from rest_framework import serializers

from order.models import Order, Trade


class OrderDetailFullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('id', 'order_type', 'quantity', 'status', 'avg_order_price', 'avg_trade_price',
                  'traded_quantity', 'created_at', 'last_updated_at', 'order_alive')


class OrderMinimumSerializer(OrderDetailFullSerializer):
    class Meta:
        model = Order
        fields = ('id',)


class OrderDetailSerializer(OrderDetailFullSerializer):
    class Meta:
        model = Order
        fields = ('avg_order_price', 'quantity','avg_trade_price', 'traded_quantity', 'order_alive')


class TradeDetailFullSerializer(serializers.ModelSerializer):
    buy_order = OrderDetailSerializer()
    sell_order = OrderDetailSerializer()

    class Meta:
        model = Trade
        fields = ('id', 'avg_trade_price', 'quantity', 'buy_order', 'sell_order', 'created_at')

class TradeDetailSerializer(TradeDetailFullSerializer):
    buy_order_id = serializers.SerializerMethodField()
    sell_order_id = serializers.SerializerMethodField()

    class Meta:
        model = Trade
        fields = ('id', 'avg_trade_price', 'quantity', 'buy_order_id', 'sell_order_id', 'created_at')

    @staticmethod
    def get_buy_order_id(obj):
        return obj.buy_order.id

    @staticmethod
    def get_sell_order_id(obj):
        return obj.sell_order.id
