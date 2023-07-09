from django.urls import path, include
from rest_framework import routers

from tables.views import TableView, CreateRowView, GetAllRowView

router = routers.DefaultRouter()
router.register('', TableView)

urlpatterns = [
    path('', include(router.urls), name='table'),
    path('<int:pk>/row/', CreateRowView.as_view(), name='create-row'),
    path('<int:pk>/rows/', GetAllRowView.as_view(), name='get-rows')
]
