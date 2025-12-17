# rooms/forms.py
from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField

from .models import Room, Reservation, Building, Floor
from .utils import format_room_option


# ---------------------------------------------------------
# ROOM ADMIN FORM — floor becomes numeric instead of dropdown
# ---------------------------------------------------------
class RoomAdminForm(forms.ModelForm):
    # Override floor: numeric <input> instead of ForeignKey dropdown
    floor = forms.IntegerField(
        required=False,
        label="Floor number",
        widget=forms.NumberInput(attrs={"min": 1}),
        help_text="Enter the floor number (the system will create it automatically).",
    )

    class Meta:
        model = Room
        fields = "__all__"

    def clean_floor(self):
        """
        Convert the numeric floor input into a Floor instance.
        Automatically creates a Floor object under the selected building.
        """
        floor_number = self.cleaned_data.get("floor")
        building = self.cleaned_data.get("building")

        # If no floor number or no building selected yet
        if not floor_number or not building:
            return None

        # Try to get or create the floor for this building
        floor_obj, created = Floor.objects.get_or_create(
            building=building,
            number=floor_number
        )
        return floor_obj


# ---------------------------------------------------------
# RESERVATION ADMIN FORM (your original logic preserved 100%)
# ---------------------------------------------------------
class ReservationAdminForm(forms.ModelForm):
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

        # Attach rooms AJAX URL (unchanged)
        try:
            rooms_url = reverse("rooms_for_building")
        except Exception:
            rooms_url = ""
        self.fields["building"].widget.attrs["data-rooms-url"] = rooms_url

        # --------------------------------------------------
        # 🔒 IMPORTANT RULE:
        # Editing → DO NOT restrict queryset
        # Adding → restrict by building
        # --------------------------------------------------

        if self.instance.pk:
            # ✅ Editing existing reservation
            # Let Django Admin handle selected room naturally
            self.fields["room"].queryset = Room.objects.all()

            if self.instance.room:
                self.initial["building"] = self.instance.room.building_id

        else:
            # ✅ Adding new reservation
            building_id = self.data.get("building")

            if building_id:
                self.fields["room"].queryset = (
                    Room.objects.filter(building_id=building_id)
                    .select_related("floor")
                    .annotate(_num_int=Cast("number", IntegerField()))
                    .order_by("floor__number", "_num_int", "number")
                )
                self.initial["building"] = building_id
            else:
                self.fields["room"].queryset = Room.objects.none()

        self.fields["room"].label_from_instance = format_room_option

