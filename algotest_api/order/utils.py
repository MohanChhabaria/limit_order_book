from decimal import Decimal, ROUND_DOWN
from distutils.util import strtobool

from order.enums import OrderStatus
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from order.models import Order


def update_order(trade_price : float, trade_quantity: int, order : 'Order'):
    order_avg_trade_price = order.avg_trade_price or 0.0
    order_traded_quantity = order.traded_quantity or 0

    new_traded_quantity = order_traded_quantity + trade_quantity
    new_avg_trade_price = ((order_avg_trade_price * order_traded_quantity) + (trade_price * trade_quantity)) / new_traded_quantity
    order.avg_trade_price = new_avg_trade_price
    order.traded_quantity = new_traded_quantity
    if new_traded_quantity == order.quantity:
        order.status = OrderStatus.FILLED
        order.order_alive = False
    elif new_traded_quantity < order.quantity:
        order.status = OrderStatus.PARTIALLY_FILLED
    else:
        raise ValueError("Traded quantity cannot exceed order quantity")
    order.save(update_fields=['avg_trade_price', 'traded_quantity', 'status', 'order_alive'])


def round_upto_two_decimal_places(value: float) -> float:
    return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def safe_convert_to_bool(val: Any) -> bool | None:
    """
    Safely convert a value to a boolean.
    """
    if val is None:
        return val
    if isinstance(val, str):
        try:
            return strtobool(val)
        except ValueError:
            return None
    return bool(val)