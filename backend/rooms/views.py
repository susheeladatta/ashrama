# rooms/views.py - UPDATED
from datetime import date

from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models.functions import Cast
from django.db.models import IntegerField, Q, Exists, OuterRef
from django.views.decorators.http import require_GET

from .models import Room, Building, Reservation
from .utils import format_room_option


@require_GET
def rooms_for_building(request):
    """
    AJAX endpoint used by the admin JS.
    Expects query param `building` (id). Returns JSON:
      { "results": [ {"id": <pk>, "text": "<label>"}, ... ] }
    
    Returns only rooms that are actually available (not occupied, not under repair, etc.)
    """
    building_id = request.GET.get("building")
    if not building_id:
        return JsonResponse({"results": []})

    # verify building exists
    try:
        building = Building.objects.get(pk=building_id)
    except Building.DoesNotExist:
        return HttpResponseBadRequest("Invalid building")
    
    today = date.today()
    
    # Get all rooms for this building
    rooms = Room.objects.filter(building_id=building_id)
    
    # Create a subquery for active reservations
    active_reservation = Exists(
        Reservation.objects.filter(
            room=OuterRef("pk"),
            is_cancelled=False,
            check_in_date__lte=today,
            check_out_date__gt=today,
        )
    )
    
    # Annotate rooms with whether they're occupied
    rooms = rooms.annotate(is_occupied=active_reservation)
    
    # Filter for rooms that are actually available:
    # 1. is_available = True
    # 2. needs_repair = False
    # 3. needs_cleaning = False  
    # 4. No active reservation (is_occupied = False)
    available_rooms = rooms.filter(
        is_available=True,
        needs_repair=False,
        needs_cleaning=False,
        is_occupied=False
    )
    
    qs = (
        available_rooms
        .select_related("floor")
        .annotate(_num_int=Cast("number", IntegerField()))
        .order_by("floor__number", "_num_int", "number")
    )

    results = [{"id": r.pk, "text": format_room_option(r)} for r in qs]
    return JsonResponse({"results": results})