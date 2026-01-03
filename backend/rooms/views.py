# rooms/views.py
from datetime import date

from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models.functions import Cast
from django.db.models import IntegerField, Exists, OuterRef
from django.utils.html import strip_tags
from django.views.decorators.http import require_GET

from .models import Room, Building, Reservation
from .utils import format_room_option


@require_GET
def rooms_for_building(request):
    """
    AJAX endpoint used by the admin JS.
    Expects query param `building` (id). Returns JSON:
      { "results": [ {"id": <pk>, "text": "<label>"}, ... ] }
    """
    building_id = request.GET.get("building")
    reservation_id = request.GET.get("reservation_id")
    
    if not building_id:
        return JsonResponse({"results": []})

    # verify building exists
    try:
        Building.objects.only("id").get(pk=building_id)
    except Building.DoesNotExist:
        return HttpResponseBadRequest("Invalid building")

    # Get today's date
    today = date.today()
    
    # Check for active reservations (not cancelled, spanning today)
    active_reservation = Exists(
        Reservation.objects.filter(
            room=OuterRef("pk"),
            is_cancelled=False,
            check_in_date__lte=today,
            check_out_date__gt=today,
        )
    )
    
    # Get rooms in this building
    rooms = Room.objects.filter(building_id=building_id)
    
    # Annotate with active reservation info
    rooms = rooms.annotate(has_active_reservation=active_reservation)
    
    # For editing existing reservation, include the current room even if occupied
    current_room_id = None
    if reservation_id:
        try:
            reservation = Reservation.objects.get(pk=reservation_id)
            current_room_id = reservation.room_id
        except Reservation.DoesNotExist:
            pass
    
    # Filter for available rooms: not under repair, not needing cleaning, not occupied
    available_rooms = rooms.filter(
        is_available=True,
        needs_repair=False,
        needs_cleaning=False,
        has_active_reservation=False
    )
    
    # If editing, include the current room
    if current_room_id:
        current_room = rooms.filter(pk=current_room_id)
        qs = (available_rooms | current_room).distinct()
    else:
        qs = available_rooms
    
    # Apply ordering
    qs = (
        qs
        .select_related("floor")
        .annotate(_num_int=Cast("number", IntegerField()))
        .order_by("floor__number", "_num_int", "number")
    )

    # Format results - convert HTML to plain text for dropdown
    results = []
    for room in qs:
        html_text = str(format_room_option(room))
        plain_text = strip_tags(html_text).strip()
        results.append({"id": room.pk, "text": plain_text})
    
    return JsonResponse({"results": results})