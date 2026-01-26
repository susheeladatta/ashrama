# rooms/views.py
from datetime import date, datetime

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
    
    # For editing existing reservation, get the current room
    current_room_id = None
    if reservation_id:
        try:
            reservation = Reservation.objects.get(pk=reservation_id)
            current_room_id = reservation.room_id
        except Reservation.DoesNotExist:
            pass
    
    # Check for overlapping reservations if dates are provided
    if check_in_date and check_out_date:
        # Check for reservations that overlap with the given date range
        # Condition: reservation ends after check-in AND starts before check-out
        # AND is not cancelled AND not checked out
        overlapping_reservation = Exists(
            Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                is_checked_out=False,
                check_out_date__gt=check_in_date,
                check_in_date__lt=check_out_date,
            )
        )
        
        # When editing, exclude the current reservation from overlap check
        if reservation_id and current_room_id:
            overlapping_reservation = Exists(
                Reservation.objects.filter(
                    room=OuterRef("pk"),
                    is_cancelled=False,
                    is_checked_out=False,
                    check_out_date__gt=check_in_date,
                    check_in_date__lt=check_out_date,
                ).exclude(pk=reservation_id)
            )
        
        # Annotate with overlapping reservation info
        rooms = rooms.annotate(has_overlapping_reservation=overlapping_reservation)
    else:
        # If no dates provided, fall back to checking active reservations for today
        today = date.today()
        
        # Check for active reservations (not cancelled, not checked out, spanning today)
        overlapping_reservation = Exists(
            Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lte=today,
                check_out_date__gt=today,
            )
        )
        
        # When editing, exclude the current reservation
        if reservation_id and current_room_id:
            overlapping_reservation = Exists(
                Reservation.objects.filter(
                    room=OuterRef("pk"),
                    is_cancelled=False,
                    is_checked_out=False,
                    check_in_date__lte=today,
                    check_out_date__gt=today,
                ).exclude(pk=reservation_id)
            )
        
        # Annotate with overlapping reservation info
        rooms = rooms.annotate(has_overlapping_reservation=overlapping_reservation)
    
    # Filter for available rooms: not under repair, not needing cleaning
    available_rooms = rooms.filter(
        is_available=True,
        needs_repair=False,
        needs_cleaning=False,
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
        # Check if room is occupied
        is_occupied = getattr(room, 'has_overlapping_reservation', False)
        
        # Get the base room info - call format_room_option with the room object
        html_text = str(format_room_option(room))
        
        # Debug: print the HTML text to see what format_room_option returns
        # print(f"Room {room.id}: HTML text: {html_text}")
        
        # Convert to plain text
        plain_text = strip_tags(html_text).strip()
        
        # Check if the room should be marked as occupied
        # Look for "Available" in the text (case-insensitive)
        if is_occupied:
            # Replace "Available" with "Occupied" regardless of case
            plain_text_lower = plain_text.lower()
            if "available" in plain_text_lower:
                # Find the position and preserve original case for the rest of the text
                index = plain_text_lower.find("available")
                plain_text = plain_text[:index] + "Occupied" + plain_text[index + len("available"):]
            
            # Also replace the emoji if present
            if "🍀" in plain_text:
                plain_text = plain_text.replace("🍀", "🍟")
            elif "💬" in plain_text:  # Check for other emoji variants
                plain_text = plain_text.replace("💬", "🍟")
            elif "💭" in plain_text:  # Check for other emoji variants
                plain_text = plain_text.replace("💭", "🍟")
        
        results.append({
            "id": room.pk, 
            "text": plain_text,
            "occupied": is_occupied
        })
    
    return JsonResponse({"results": results})