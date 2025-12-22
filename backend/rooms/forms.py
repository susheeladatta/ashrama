# rooms/forms.py - FINAL WORKING VERSION
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
# RESERVATION ADMIN FORM - ULTIMATE FIX
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

        # Get the current reservation instance
        instance = self.instance
        
        # Set initial values based on the instance
        if instance and instance.pk and instance.room_id:
            # Try to get the room with its building
            try:
                room = Room.objects.select_related('building').get(pk=instance.room_id)
                # Set the building initial value
                self.initial['building'] = room.building_id
                # Set the room initial value
                self.initial['room'] = room.pk
            except Room.DoesNotExist:
                pass
        elif instance and instance.pk:
            # Instance exists but has no room - this shouldn't happen but handle it
            self.initial['room'] = None
        
        # Get building ID for filtering
        building_id = None
        if self.data and 'building' in self.data and self.data['building']:
            # Use POST/GET data if available
            try:
                building_id = int(self.data['building'])
            except (ValueError, TypeError):
                pass
        elif 'building' in self.initial:
            # Otherwise use initial value
            building_id = self.initial.get('building')
        
        # Build the room queryset
        # CRITICAL: When editing, ALWAYS include the current room
        current_room_id = None
        if instance and instance.pk and instance.room_id:
            current_room_id = instance.room_id
        
        if building_id:
            # Filter by building, but include current room if it exists
            if current_room_id:
                room_qs = Room.objects.filter(
                    Q(building_id=building_id) | Q(pk=current_room_id)
                ).distinct()
            else:
                room_qs = Room.objects.filter(building_id=building_id)
        else:
            # No building selected - show all rooms
            room_qs = Room.objects.all()
        
        # Apply ordering
        self.fields["room"].queryset = (
            room_qs
            .select_related("floor")
            .annotate(_num_int=Cast("number", IntegerField()))
            .order_by("floor__number", "_num_int", "number")
        )

        self.fields["room"].label_from_instance = format_room_option
        
        # DEBUG: Print the initial room value
        # print(f"DEBUG: Initial room value: {self.initial.get('room')}")
        # print(f"DEBUG: Current room ID: {current_room_id}")

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data