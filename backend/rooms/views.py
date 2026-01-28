# rooms/views.py
from datetime import date, datetime

from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models.functions import Cast
from django.db.models import IntegerField, Q
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
    check_in_date_str = request.GET.get("check_in_date")
    check_out_date_str = request.GET.get("check_out_date")
    
    if not building_id:
        return JsonResponse({"results": []})

    # verify building exists
    try:
        Building.objects.only("id").get(pk=building_id)
    except Building.DoesNotExist:
        return HttpResponseBadRequest("Invalid building")

    # Parse check-in and check-out dates
    check_in_date = None
    check_out_date = None
    
    if check_in_date_str:
        try:
            check_in_date = datetime.strptime(check_in_date_str, "%Y-%m-%d").date()
        except ValueError:
            # If invalid date format, ignore and fall back
            pass
    
    if check_out_date_str:
        try:
            check_out_date = datetime.strptime(check_out_date_str, "%Y-%m-%d").date()
        except ValueError:
            # If invalid date format, ignore and fall back
            pass

    # Get rooms in this building
    rooms = Room.objects.filter(building_id=building_id)
    
    # Filter for available rooms: not under repair, not needing cleaning
    available_rooms = rooms.filter(
        is_available=True,
        needs_repair=False,
        needs_cleaning=False,
    )
    
    # For editing existing reservation, get the current room
    current_room_id = None
    if reservation_id:
        try:
            reservation = Reservation.objects.get(pk=reservation_id)
            current_room_id = reservation.room_id
        except Reservation.DoesNotExist:
            pass
    
    # If editing, include the current room (even if under repair or needs cleaning)
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
        is_occupied = False
        
        # Only check occupancy if dates are provided
        if check_in_date and check_out_date:
            # Check for overlapping reservations that are not cancelled and not checked out
            overlapping_reservations = Reservation.objects.filter(
                room=room,
                is_cancelled=False,
                is_checked_out=False,
            ).filter(
                # The date range overlaps if:
                # 1. Reservation starts before the new check-out date AND
                # 2. Reservation ends after the new check-in date
                Q(check_in_date__lt=check_out_date) & Q(check_out_date__gt=check_in_date)
            )
            
            # When editing, exclude the current reservation
            if reservation_id:
                overlapping_reservations = overlapping_reservations.exclude(pk=reservation_id)
            
            # If there are any overlapping reservations, the room is occupied
            is_occupied = overlapping_reservations.exists()
        
        # Get the base room info
        html_text = str(format_room_option(room))
        plain_text = strip_tags(html_text).strip()
        
        # If the room is occupied for the selected dates, mark it as Occupied
        if is_occupied:
            # Replace "Available" with "Occupied" (case-insensitive)
            import re
            plain_text = re.sub(r'available', 'Occupied', plain_text, flags=re.IGNORECASE)
            
            # Also replace emojis
            plain_text = plain_text.replace("🍀", "🍟")
            plain_text = plain_text.replace("💬", "🍟")
            plain_text = plain_text.replace("💭", "🍟")
        
        results.append({
            "id": room.pk, 
            "text": plain_text,
            "occupied": is_occupied
        })
    
    return JsonResponse({"results": results})