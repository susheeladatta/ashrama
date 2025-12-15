# rooms/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import RoomViewSet, BuildingViewSet, FloorViewSet, GuestViewSet, ReservationViewSet
from admin_notification.views import check_notification_view
from .views import rooms_for_building

router = DefaultRouter()
router.register(r'rooms', RoomViewSet)
router.register(r'buildings', BuildingViewSet)
router.register(r'floors', FloorViewSet)
router.register(r'guests', GuestViewSet)
router.register(r'reservations', ReservationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('check/notification', check_notification_view, name='check_notifications'),
    # NEW: admin AJAX endpoint to populate rooms based on building
    path('rooms-for-building/', rooms_for_building, name='rooms_for_building'),
]
