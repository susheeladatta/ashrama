# rooms/forms.py
from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField

from .models import Room, Reservation, Building
from .utils import format_room_option


class RoomAdminForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = "__all__"


class ReservationAdminForm(forms.ModelForm):
    """
    Admin form: building selector provides `data-rooms-url`.
    Room queryset is EMPTY by default; JS populates it when building is chosen.
    When editing an instance, pre-populate building and rooms for that reservation.
    """
    building = forms.ModelChoiceField(
        queryset=Building.objects.all().order_by("name"),
        required=False,
        label="Building",
        help_text="Select a building first to filter the room list.",
    )

    class Meta:
        model = Reservation
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Resolve the URL for the AJAX endpoint and attach it to the building widget
        try:
            rooms_url = reverse("rooms_for_building")
        except Exception:
            rooms_url = ""
        if "building" in self.fields:
            self.fields["building"].widget.attrs["data-rooms-url"] = rooms_url

        # Default: no rooms shown until building selected (prevents duplicates/all-rooms)
        self.fields["room"].queryset = Room.objects.none()

        # If editing an existing reservation, populate building and rooms
        if self.instance and getattr(self.instance, "pk", None):
            room = getattr(self.instance, "room", None)
            if room:
                b = room.building
                self.fields["building"].initial = b
                # Rooms only from that building, ordered by floor number and numeric room number
                self.fields["room"].queryset = (
                    Room.objects.filter(building=b)
                    .select_related("floor")
                    .annotate(_num_int=Cast("number", IntegerField()))
                    .order_by("floor__number", "_num_int", "number")
                )

        # Always use the pretty label for the room field (server-rendered fallback)
        self.fields["room"].label_from_instance = format_room_option
