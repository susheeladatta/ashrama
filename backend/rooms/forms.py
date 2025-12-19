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
# RESERVATION ADMIN FORM - FIXED WITHOUT UNION ISSUES
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

        # Get current room from instance if it exists
        current_room_id = None
        if self.instance and self.instance.pk and self.instance.room_id:
            current_room_id = self.instance.room_id
            try:
                current_room = self.instance.room
                # Set initial building value based on current room
                if current_room and current_room.building_id:
                    self.initial['building'] = current_room.building_id
            except Room.DoesNotExist:
                current_room = None

        # Determine which building to use for filtering
        # Priority: POST data > initial building > None
        building_id = None
        if self.data and 'building' in self.data and self.data['building']:
            # Form is being submitted or AJAX request
            try:
                building_id = int(self.data['building'])
            except (ValueError, TypeError):
                pass
        elif 'building' in self.initial and self.initial['building']:
            # Initial value from instance
            building_id = self.initial['building']

        # Build the room queryset using Q objects instead of union
        # This is the key fix: use Q objects to combine conditions
        conditions = Q()
        
        if building_id:
            # Add condition for rooms in the selected building
            conditions |= Q(building_id=building_id)
        
        # CRITICAL: Always include the current room if it exists
        # This ensures the room appears in the dropdown
        if current_room_id:
            conditions |= Q(pk=current_room_id)
        
        # If no conditions, get all rooms
        if not conditions:
            conditions = Q()  # Empty Q object will match all
        
        # Build the queryset with the combined conditions
        room_qs = Room.objects.filter(conditions).distinct()
        
        # Apply ordering and formatting
        self.fields["room"].queryset = (
            room_qs
            .select_related("floor")
            .annotate(_num_int=Cast("number", IntegerField()))
            .order_by("floor__number", "_num_int", "number")
        )

        self.fields["room"].label_from_instance = format_room_option

    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure the room field gets the correct value
        room = cleaned_data.get('room')
        if room and self.instance and self.instance.pk:
            # Update the building field based on the selected room
            building = cleaned_data.get('building')
            if not building and room.building:
                cleaned_data['building'] = room.building
        
        return cleaned_data