from django import forms
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models import Q

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
    )

    class Meta:
        model = Room
        fields = "__all__"

    def clean_floor(self):
        floor_number = self.cleaned_data.get("floor")
        building = self.cleaned_data.get("building")

        if not floor_number or not building:
            return None

        floor_obj, _ = Floor.objects.get_or_create(
            building=building,
            number=floor_number
        )
        return floor_obj


# ---------------------------------------------------------
# RESERVATION ADMIN FORM - HOTEL STYLE
# ---------------------------------------------------------
class ReservationAdminForm(forms.ModelForm):
    """
    Hotel-style reservation form:
    1. Select Building
    2. Select Room (with availability for the selected room)
    3. Select dates on calendar
    """
    building = forms.ModelChoiceField(
        queryset=Building.objects.all(),
        required=False,
        label="Building",
        empty_label="--- Select Building ---"
    )

    class Meta:
        model = Reservation
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up the building field with AJAX URL
        try:
            self.fields["building"].widget.attrs["data-rooms-url"] = reverse("rooms_for_building")
        except Exception:
            pass

        instance = self.instance

        # Restore building on edit
        if instance.pk and instance.room_id:
            try:
                self.initial["building"] = instance.room.building_id
            except Exception:
                pass

        # Get selected building
        building_id = self.data.get("building") or self.initial.get("building")
        
        # Get selected room
        room_id = self.data.get("room") or self.initial.get("room")

        # Get dates if available
        check_in = self.data.get("check_in_date") or self.initial.get("check_in_date")
        check_out = self.data.get("check_out_date") or self.initial.get("check_out_date")

        # Filter rooms by building
        rooms = Room.objects.all()
        if building_id:
            rooms = rooms.filter(building_id=building_id)

        # Check occupancy for the selected room only
        occupied_ids = set()
        if room_id and check_in and check_out:
            conflicts = Reservation.objects.filter(
                room_id=room_id,
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lt=check_out,
                check_out_date__gt=check_in,
            )

            if instance.pk:
                conflicts = conflicts.exclude(pk=instance.pk)

            if conflicts.exists():
                occupied_ids.add(room_id)

        self.fields["room"].queryset = rooms

        def room_label(room):
            base = format_room_option(room)
            if room.id in occupied_ids:
                # Replace any variant of "Available" with "Occupied" (case-insensitive)
                import re
                base = re.sub(r'Available', 'Occupied', base, flags=re.IGNORECASE)
                # Replace various emoji with occupied emoji
                base = base.replace("🍀", "🍟")
                base = base.replace("💬", "🍟")
                base = base.replace("💭", "🍟")
            return base

        self.fields["room"].label_from_instance = room_label

    # ---------------------------------------------------
    # HARD BLOCK ON SAVE
    # ---------------------------------------------------
    def clean(self):
        cleaned = super().clean()

        room = cleaned.get("room")
        check_in = cleaned.get("check_in_date")
        check_out = cleaned.get("check_out_date")

        # Ensure all required fields are present
        if not room or not check_in or not check_out:
            raise ValidationError("Building, Room, Check-in date, and Check-out date are required.")

        # Check date logic
        if check_in >= check_out:
            raise ValidationError("Check-in date must be before check-out date.")

        # Check for conflicting reservations
        conflicts = Reservation.objects.filter(
            room=room,
            is_cancelled=False,
            is_checked_out=False,
            check_in_date__lt=check_out,
            check_out_date__gt=check_in,
        )

        # Exclude the current reservation if editing
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)

        if conflicts.exists():
            conflicting_res = conflicts.first()
            raise ValidationError(
                f"Room is occupied from {conflicting_res.check_in_date} to {conflicting_res.check_out_date}. "
                f"Please choose different dates or a different room."
            )

        return cleaned