import os

REDIS_URL      = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
ORDERS_STREAM  = os.getenv("ORDERS_STREAM", "orders_stream")
TRADES_STREAM  = os.getenv("TRADES_STREAM", "trades_stream")
ORDERS_GROUP   = os.getenv("ORDERS_GROUP", "order_matcher")
ORDERS_CONSUMER= os.getenv("ORDERS_CONSUMER", "order_matcher1")