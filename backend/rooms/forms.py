# rooms/forms.py
from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField, Q

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
# RESERVATION ADMIN FORM - FIXED
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

        # Get the current room from the instance if it exists
        instance_room = None
        if self.instance and self.instance.pk and self.instance.room_id:
            instance_room = self.instance.room
        
        # Initialize building from the instance's room if available
        if instance_room and instance_room.building_id:
            self.initial['building'] = instance_room.building_id
            building_id = instance_room.building_id
        else:
            # Try to get building from POST/GET data
            building_id = self.data.get("building") if self.data else None
        
        # Build the room queryset
        room_qs = Room.objects.all()
        
        # If we have a building ID, filter by it
        if building_id:
            room_qs = room_qs.filter(building_id=building_id)
        
        # ALWAYS include the current room in the queryset if it exists
        # This is crucial for the edit form to show the selected room
        if instance_room:
            # Create a union queryset that includes the current room
            room_qs = (room_qs | Room.objects.filter(pk=instance_room.pk)).distinct()
        
        # Apply ordering and formatting
        self.fields["room"].queryset = (
            room_qs
            .select_related("floor")
            .annotate(_num_int=Cast("number", IntegerField()))
            .order_by("floor__number", "_num_int", "number")
            .distinct()
        )

        self.fields["room"].label_from_instance = format_room_option
    
    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get('room')
        
        # If we're editing and room exists, ensure building matches room's building
        if self.instance and self.instance.pk and room:
            building = cleaned_data.get('building')
            if not building and room.building:
                # Set building based on the room
                cleaned_data['building'] = room.building
        
        return cleaned_data