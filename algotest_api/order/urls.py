from django.urls import re_path
from rest_framework.urlpatterns import format_suffix_patterns

from order.views import OrderDetailView, CreateOrderAPIView, GetAllOrdersView, GetAllTradesView


app_name = 'order'

urlpatterns = [
    re_path(r'^details/(?P<order_id>\d+)/$', OrderDetailView.as_view(), name='order-detail'),
    re_path(r'^create/$', CreateOrderAPIView.as_view(), name='order-create'),
    re_path(r'^all_orders/$', GetAllOrdersView.as_view(), name='order-list'),
    re_path(r'^all_trades/$', GetAllTradesView.as_view(), name='trade-list'),
]

urlpatterns = format_suffix_patterns(urlpatterns)