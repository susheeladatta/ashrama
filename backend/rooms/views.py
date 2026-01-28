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
    Expects query params:
      building
      reservation_id (optional)
      check_in_date
      check_out_date

    Returns:
      { "results": [ {"id": <pk>, "text": "<label>", "occupied": bool}, ... ] }
    """

    building_id = request.GET.get("building")
    reservation_id = request.GET.get("reservation_id")
    check_in_date_str = request.GET.get("check_in_date")
    check_out_date_str = request.GET.get("check_out_date")

    if not building_id:
        return JsonResponse({"results": []})

    # Validate building
    try:
        Building.objects.only("id").get(pk=building_id)
    except Building.DoesNotExist:
        return HttpResponseBadRequest("Invalid building")

    # Parse dates
    check_in_date = None
    check_out_date = None

    if check_in_date_str:
        try:
            check_in_date = datetime.strptime(check_in_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    if check_out_date_str:
        try:
            check_out_date = datetime.strptime(check_out_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    rooms = Room.objects.filter(building_id=building_id)

    # Current room when editing
    current_room_id = None
    if reservation_id:
        try:
            reservation = Reservation.objects.get(pk=reservation_id)
            current_room_id = reservation.room_id
        except Reservation.DoesNotExist:
            pass

    #
    # -------- OCCUPANCY LOGIC (DATE AWARE) --------
    #
    if check_in_date and check_out_date:
        overlap_qs = Reservation.objects.filter(
            room=OuterRef("pk"),
            is_cancelled=False,
            is_checked_out=False,
            check_out_date__gt=check_in_date,
            check_in_date__lt=check_out_date,
        )

        if reservation_id:
            overlap_qs = overlap_qs.exclude(pk=reservation_id)

        rooms = rooms.annotate(has_overlapping_reservation=Exists(overlap_qs))

    else:
        # Fallback: use today if dates not chosen yet
        today = date.today()

        overlap_qs = Reservation.objects.filter(
            room=OuterRef("pk"),
            is_cancelled=False,
            is_checked_out=False,
            check_in_date__lte=today,
            check_out_date__gt=today,
        )

        if reservation_id:
            overlap_qs = overlap_qs.exclude(pk=reservation_id)

        rooms = rooms.annotate(has_overlapping_reservation=Exists(overlap_qs))

    #
    # Keep your existing availability filters
    #
    available_rooms = rooms.filter(
        is_available=True,
        needs_repair=False,
        needs_cleaning=False,
    )

    # When editing, always keep current room selectable
    if current_room_id:
        current_room = rooms.filter(pk=current_room_id)
        qs = (available_rooms | current_room).distinct()
    else:
        qs = available_rooms

    # Ordering (unchanged)
    qs = (
        qs.select_related("floor")
        .annotate(_num_int=Cast("number", IntegerField()))
        .order_by("floor__number", "_num_int", "number")
    )

    #
    # Format dropdown labels
    #
    results = []

    for room in qs:
        is_occupied = bool(getattr(room, "has_overlapping_reservation", False))

        html_text = str(format_room_option(room))
        plain_text = strip_tags(html_text).strip()

        if is_occupied:
            lower = plain_text.lower()
            if "available" in lower:
                idx = lower.find("available")
                plain_text = plain_text[:idx] + "Occupied" + plain_text[idx + len("available"):]

        results.append({
            "id": room.pk,
            "text": plain_text,
            "occupied": is_occupied,
        })

    return JsonResponse({"results": results})
