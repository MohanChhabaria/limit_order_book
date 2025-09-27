from enum import Enum

from django.db import models

class OrderType(models.IntegerChoices):
    BUY = 1, 'Buy'
    SELL = -1, 'Sell'

class OrderStatus(models.IntegerChoices):
    NEW = 1, 'New'
    PARTIALLY_FILLED = 2, 'Partially Filled'
    FILLED = 3, 'Filled'
    CANCELED = 4, 'Canceled'
