from django import forms
from django.db.models import Exists, OuterRef
from django.core.exceptions import ValidationError

from .models import Reservation, Room


class ReservationAdminForm(forms.ModelForm):

    class Meta:
        model = Reservation
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only run when dates exist
        check_in = self.initial.get("check_in_date") or self.data.get("check_in_date")
        check_out = self.initial.get("check_out_date") or self.data.get("check_out_date")
        building = self.initial.get("building") or self.data.get("building")

        room_qs = Room.objects.all()

        if building:
            room_qs = room_qs.filter(building_id=building)

        if check_in and check_out:

            overlapping = Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lt=check_out,
                check_out_date__gt=check_in,
            )

            room_qs = room_qs.annotate(
                _is_occupied=Exists(overlapping)
            )

        else:
            room_qs = room_qs.annotate(_is_occupied=forms.Value(False))

        def room_label(room):
            status = "Occupied" if getattr(room, "_is_occupied", False) else "Available"
            return f"{room} — {status} — Capacity: {room.capacity}"

        self.fields["room"].queryset = room_qs
        self.fields["room"].label_from_instance = room_label

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
            raise ValidationError(
                f"Room overlaps with existing reservation: {r} ({r.check_in_date} → {r.check_out_date})"
            )

        return cleaned
