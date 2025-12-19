# rooms/forms.py - COMPLETE REWRITE
from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField
from django.core.exceptions import ValidationError

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
# RESERVATION ADMIN FORM - COMPLETE FIX
# ---------------------------------------------------------
class ReservationAdminForm(forms.ModelForm):
    building = forms.ModelChoiceField(
        queryset=Building.objects.all().order_by("name"),
        required=False,
        label="Building",
        help_text="Select a building first to filter the room list.",
    )
    
    # This is a custom field to help with debugging
    debug_room_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Reservation
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Debug logging
        print(f"DEBUG: Form initialized with instance: {self.instance}")
        print(f"DEBUG: Instance has room_id: {getattr(self.instance, 'room_id', None)}")
        
        # Attach AJAX URL
        try:
            self.fields["building"].widget.attrs["data-rooms-url"] = reverse("rooms_for_building")
        except Exception:
            pass

        # IMPORTANT: Always get fresh room data to avoid stale references
        room_instance = None
        if self.instance and self.instance.pk and self.instance.room_id:
            try:
                # Get the room with all related data
                room_instance = Room.objects.select_related('building', 'floor').get(pk=self.instance.room_id)
                # Update the instance's room with the fresh data
                self.instance.room = room_instance
                print(f"DEBUG: Loaded room: {room_instance}")
            except Room.DoesNotExist:
                print("DEBUG: Room does not exist")
                room_instance = None
        
        # Set initial building value
        if room_instance and room_instance.building:
            self.initial['building'] = room_instance.building_id
            print(f"DEBUG: Set initial building to: {room_instance.building_id}")
        
        # Set debug field
        if self.instance.room_id:
            self.initial['debug_room_id'] = self.instance.room_id
        
        # Get building from POST data or initial
        building_id = None
        if self.data and 'building' in self.data:
            building_id = self.data.get('building')
        elif 'building' in self.initial:
            building_id = self.initial.get('building')
        
        print(f"DEBUG: Building ID for filtering: {building_id}")
        
        # Build the room queryset
        # CRITICAL: Always start with the current room if it exists
        room_ids_to_include = []
        if self.instance.room_id:
            room_ids_to_include.append(self.instance.room_id)
        
        # Create base queryset
        if room_ids_to_include:
            # Start with current room
            room_qs = Room.objects.filter(pk__in=room_ids_to_include)
            
            # Add rooms from selected building if different
            if building_id:
                room_qs = room_qs | Room.objects.filter(building_id=building_id)
        elif building_id:
            # No current room, just filter by building
            room_qs = Room.objects.filter(building_id=building_id)
        else:
            # No building selected, show limited set of rooms
            room_qs = Room.objects.all()[:50]  # Limit to avoid performance issues
        
        # Apply ordering
        room_qs = room_qs.select_related('floor', 'building').distinct()
        
        # Annotate and order
        room_qs = room_qs.annotate(_num_int=Cast("number", IntegerField()))
        room_qs = room_qs.order_by("floor__number", "_num_int", "number")
        
        print(f"DEBUG: Room queryset count: {room_qs.count()}")
        print(f"DEBUG: Room queryset includes current room: {self.instance.room_id in list(room_qs.values_list('pk', flat=True))}")
        
        self.fields["room"].queryset = room_qs
        self.fields["room"].label_from_instance = format_room_option
        
        # Force the room field to show the current room value
        if self.instance.room_id:
            self.initial['room'] = self.instance.room_id

    def clean(self):
        cleaned_data = super().clean()
        print(f"DEBUG: Cleaned data room: {cleaned_data.get('room')}")
        print(f"DEBUG: Cleaned data building: {cleaned_data.get('building')}")
        return cleaned_data