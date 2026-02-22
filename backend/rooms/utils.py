# rooms/utils.py
from __future__ import annotations

from django.utils.html import format_html
from django.utils.timezone import localdate

from .models import Room


def _status_bits(room: Room) -> str:
    needs_repair = getattr(room, "needs_repair", False)

    # Prefer a computed availability method if you have one:
    is_available_now = None
    if hasattr(room, "is_available_now"):
        try:
            is_available_now = bool(room.is_available_now())
        except Exception:
            is_available_now = None

    if is_available_now is None:
        is_available_now = bool(getattr(room, "is_available", False))

    available_from = getattr(room, "available_from_date", None)

    if needs_repair:
        return "🔧 Unavailable (Repairs)"
    if is_available_now:
        return "✅ Available"
    if available_from:
        try:
            d = localdate(available_from)
        except Exception:
            d = available_from
        return f"📅 Available from {d:%b %d, %Y}"
    return "❌ Unavailable"


def format_room_option(room):
    """
    This is used for:
    - Reservation admin dropdown
    - AJAX rooms-for-building endpoint

    IMPORTANT:
    Availability here MUST match the Room admin list
    """

    # ---- REAL availability check (same logic as admin list) ----
    today = now().date()

    has_active_reservation = Reservation.objects.filter(
        room=room,
        is_cancelled=False,
        check_in_date__lte=today,
        check_out_date__gt=today,
    ).exists()

    if has_active_reservation:
        status_label = "🧳 Occupied"
    else:
        status_label = "✅ Available"

    # ---- Safe floor handling (numeric input) ----
    floor_number = room.floor if room.floor is not None else "?"

    return (
        f"#{room.number} "
        f"(Floor {floor_number}) – "
        f"{room.get_room_type_display()} – "
        f"{status_label} – "
        f"Capacity: {room.capacity}"
    )