# rooms/forms.py - FIXED VERSION
from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField, Q

from .models import Room, Reservation, Building, Floor
from .utils import format_room_option


# ---------------------------------------------------------
# ROOM ADMIN FORM
# ---------------------------------------------------------
class RoomAdminForm(forms.ModelForm):
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
        floor_number = self.cleaned_data.get("floor")
        building = self.cleaned_data.get("building")

        if not floor_number or not building:
            return None

        floor_obj, created = Floor.objects.get_or_create(
            building=building,
            number=floor_number
        )
        return floor_obj


# ---------------------------------------------------------
# RESERVATION ADMIN FORM - WORKING FIX
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

        # Attach AJAX URL
        try:
            self.fields["building"].widget.attrs["data-rooms-url"] = reverse("rooms_for_building")
        except Exception:
            pass

        # Get current room ID from instance
        current_room_id = None
        if self.instance and self.instance.pk and self.instance.room_id:
            current_room_id = self.instance.room_id

        # Set initial building value from current room's building
        if current_room_id:
            try:
                current_room = Room.objects.get(pk=current_room_id)
                self.initial['building'] = current_room.building_id
            except Room.DoesNotExist:
                pass

        # Get building ID from data or initial
        building_id = None
        if self.data and 'building' in self.data and self.data['building']:
            try:
                building_id = int(self.data['building'])
            except (ValueError, TypeError):
                pass
        elif 'building' in self.initial:
            building_id = self.initial.get('building')

        # Build room queryset - SIMPLE and CORRECT approach
        # Always get all rooms, but ensure current room is included
        if building_id:
            # Get rooms from selected building
            room_qs = Room.objects.filter(building_id=building_id)
            
            # If editing, always include the current room
            if current_room_id:
                room_qs = Room.objects.filter(
                    Q(building_id=building_id) | Q(pk=current_room_id)
                )
        else:
            # No building selected, get all rooms
            room_qs = Room.objects.all()

        # Apply ordering
        self.fields["room"].queryset = (
            room_qs
            .select_related("floor")
            .annotate(_num_int=Cast("number", IntegerField()))
            .order_by("floor__number", "_num_int", "number")
            .distinct()
        )

        self.fields["room"].label_from_instance = format_room_option