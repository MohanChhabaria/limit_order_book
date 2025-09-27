from django.contrib import admin

from order.models import Order, Trade, Outbox


class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_type', 'status', 'avg_order_price', 'quantity',
                    'avg_trade_price', 'traded_quantity', 'order_alive', 'created_at', 'last_updated_at')

admin.site.register(Order, OrderAdmin)

class TradeAdmin(admin.ModelAdmin):
    list_display = ('buy_order', 'sell_order', 'avg_trade_price', 'quantity', 'created_at')

admin.site.register(Trade, TradeAdmin)

class OutboxAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'order_id', 'version', 'payload_text', 'created_at')

admin.site.register(Outbox, OutboxAdmin)
