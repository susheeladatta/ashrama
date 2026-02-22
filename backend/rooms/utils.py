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


def format_room_option(room: Room) -> str:
    """
    Example:  "#1 (Floor 1) – Private room – ✅ Available – Capacity: 3"
    """
    number = getattr(room, "number", "")
    floor_no = getattr(getattr(room, "floor", None), "number", "")
    try:
        room_type = room.get_room_type_display()
    except Exception:
        room_type = str(getattr(room, "room_type", ""))

    capacity = getattr(room, "capacity", None)
    capacity_bit = f" – Capacity: {capacity}" if capacity not in (None, "") else ""
    status = _status_bits(room)

    return format_html(
        "#{} (Floor {}) – {} – {}{}",
        number,
        floor_no,
        room_type,
        status,
        capacity_bit,
    )
