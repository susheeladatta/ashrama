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
# RESERVATION ADMIN FORM
# ---------------------------------------------------------
class ReservationAdminForm(forms.ModelForm):
    building = forms.ModelChoiceField(
        queryset=Building.objects.all(),
        required=False,
        label="Building",
    )

    class Meta:
        model = Reservation
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

        building_id = self.data.get("building") or self.initial.get("building")
        check_in = self.data.get("check_in_date") or self.initial.get("check_in_date")
        check_out = self.data.get("check_out_date") or self.initial.get("check_out_date")

        rooms = Room.objects.all()

        if building_id:
            rooms = rooms.filter(building_id=building_id)

        # ---------------------------------------------------
        # SIMPLE OCCUPANCY CHECK (Python, not ORM magic)
        # ---------------------------------------------------
        occupied_ids = set()

        if check_in and check_out:
            conflicts = Reservation.objects.filter(
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lt=check_out,
                check_out_date__gt=check_in,
            )

            if instance.pk:
                conflicts = conflicts.exclude(pk=instance.pk)

            occupied_ids = set(conflicts.values_list("room_id", flat=True))

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

        if not room or not check_in or not check_out:
            return cleaned

        conflicts = Reservation.objects.filter(
            room=room,
            is_cancelled=False,
            is_checked_out=False,
            check_in_date__lt=check_out,
            check_out_date__gt=check_in,
        )

        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.pk)

        if conflicts.exists():
            r = conflicts.first()
            guests = ", ".join(g.full_name for g in r.guests.all())
            raise ValidationError(
                f"Room already occupied by {guests} "
                f"from {r.check_in_date} to {r.check_out_date}"
            )

        return cleaned