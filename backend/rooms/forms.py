from django import forms
from django.urls import reverse
from django.db.models.functions import Cast
from django.db.models import IntegerField, Q, Exists, OuterRef, Value, BooleanField
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
# RESERVATION ADMIN FORM
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

        instance = self.instance

        # ---------------------------
        # Preserve existing initial logic
        # ---------------------------
        if instance and instance.pk and instance.room_id:
            try:
                room = Room.objects.select_related("building").get(pk=instance.room_id)
                self.initial["building"] = room.building_id
                self.initial["room"] = room.pk
            except Room.DoesNotExist:
                pass

        building_id = None
        if self.data and self.data.get("building"):
            try:
                building_id = int(self.data["building"])
            except Exception:
                pass
        elif "building" in self.initial:
            building_id = self.initial.get("building")

        current_room_id = instance.room_id if instance and instance.pk else None

        if building_id:
            if current_room_id:
                room_qs = Room.objects.filter(
                    Q(building_id=building_id) | Q(pk=current_room_id)
                ).distinct()
            else:
                room_qs = Room.objects.filter(building_id=building_id)
        else:
            room_qs = Room.objects.all()

        # -------------------------------------------------
        # Date-aware occupancy annotation
        # -------------------------------------------------
        check_in = self.data.get("check_in_date") or getattr(instance, "check_in_date", None)
        check_out = self.data.get("check_out_date") or getattr(instance, "check_out_date", None)

        if check_in and check_out:
            overlapping = Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                check_in_date__lt=check_out,
                check_out_date__gt=check_in,
            )

            # Exclude self when editing
            if instance and instance.pk:
                overlapping = overlapping.exclude(pk=instance.pk)

            room_qs = room_qs.annotate(
                _is_occupied=Exists(overlapping)
            )
        else:
            # ✅ FIXED: use django.db.models.Value / BooleanField (not forms.models)
            room_qs = room_qs.annotate(
                _is_occupied=Value(False, output_field=BooleanField())
            )

        self.fields["room"].queryset = (
            room_qs
            .select_related("floor")
            .annotate(_num_int=Cast("number", IntegerField()))
            .order_by("floor__number", "_num_int", "number")
        )

        # -------------------------------------------------
        # Show real status in dropdown
        # -------------------------------------------------
        def room_label(room):
            base = format_room_option(room)
            if getattr(room, "_is_occupied", False):
                return base.replace("Available", "Occupied")
            return base

        self.fields["room"].label_from_instance = room_label

    # -------------------------------------------------
    # Hard validation on save (overlap protection)
    # -------------------------------------------------
    def clean(self):
        cleaned = super().clean()

        room = cleaned.get("room")
        check_in = cleaned.get("check_in_date")
        check_out = cleaned.get("check_out_date")

        if not room or not check_in or not check_out:
            return cleaned

        qs = Reservation.objects.filter(
            room=room,
            is_cancelled=False,
            check_in_date__lt=check_out,
            check_out_date__gt=check_in,
        )

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        conflict = qs.select_related("room").first()

        if conflict:
            guests = ", ".join(g.full_name for g in conflict.guests.all())
            raise ValidationError(
                f"Room overlaps with existing reservation: {guests} "
                f"({conflict.check_in_date} → {conflict.check_out_date})"
            )

        return cleaned
