# forms.py - Simplified fix
from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField

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
# RESERVATION ADMIN FORM - SIMPLE WORKING SOLUTION
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

        # Attach AJAX URL for building-room filtering
        try:
            self.fields["building"].widget.attrs["data-rooms-url"] = reverse("rooms_for_building")
        except Exception:
            pass

        # STEP 1: Get current room and building
        current_room = None
        current_room_id = None
        current_building_id = None
        
        if self.instance and self.instance.pk:
            # Try to get room from prefetched data or fresh query
            if hasattr(self.instance, 'room') and self.instance.room:
                current_room = self.instance.room
            elif self.instance.room_id:
                try:
                    current_room = Room.objects.get(pk=self.instance.room_id)
                except Room.DoesNotExist:
                    pass
            
            if current_room:
                current_room_id = current_room.pk
                current_building_id = current_room.building_id if current_room.building else None
        
        # STEP 2: Set initial building value
        if current_building_id:
            self.initial['building'] = current_building_id
        
        # STEP 3: Determine building for filtering
        building_id = None
        if self.data and 'building' in self.data and self.data['building']:
            # Use building from POST/GET data if available
            try:
                building_id = int(self.data['building'])
            except (ValueError, TypeError):
                pass
        elif current_building_id:
            # Otherwise use the building from current room
            building_id = current_building_id
        
        # STEP 4: Build room queryset that ALWAYS includes current room
        if building_id:
            # Get rooms from selected building PLUS current room
            if current_room_id:
                # Use Q objects to combine conditions safely
                from django.db.models import Q
                room_qs = Room.objects.filter(
                    Q(building_id=building_id) | Q(pk=current_room_id)
                ).distinct()
            else:
                room_qs = Room.objects.filter(building_id=building_id)
        else:
            # No building selected, show all rooms
            room_qs = Room.objects.all()
        
        # STEP 5: Apply ordering
        self.fields["room"].queryset = (
            room_qs
            .select_related("floor")
            .annotate(_num_int=Cast("number", IntegerField()))
            .order_by("floor__number", "_num_int", "number")
        )

        self.fields["room"].label_from_instance = format_room_option

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data