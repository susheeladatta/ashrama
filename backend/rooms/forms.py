from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Reservation, Room, Building, Floor
from dal import autocomplete

class RoomAdminForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = '__all__'
        widgets = {
            'floor': autocomplete.ModelSelect2(url='floor-autocomplete', forward=['building']),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get building and floor from instance or form data
        building_id = None
        floor_id = None
        
        if self.instance and self.instance.pk:
            # Editing existing room
            if self.instance.building:
                building_id = self.instance.building.id
            if self.instance.floor:
                floor_id = self.instance.floor.id
        elif 'building' in self.data and 'floor' in self.data:
            # Form submission with data
            building_id = self.data.get('building')
            floor_id = self.data.get('floor')
        
        # Filter room types based on floor's allowed types
        if floor_id:
            try:
                floor = Floor.objects.get(id=floor_id)
                if hasattr(floor, 'allowed_room_types') and floor.allowed_room_types:
                    # Filter choices based on floor's allowed room types
                    allowed_types = floor.allowed_room_types
                    filtered_choices = [
                        (code, label) for code, label in Room.ROOM_TYPES 
                        if code in allowed_types
                    ]
                    self.fields['room_type'].choices = filtered_choices
            except (Floor.DoesNotExist, ValueError):
                pass
        elif building_id:
            # Fallback: filter based on building type if floor not selected
            try:
                building = Building.objects.get(id=building_id)
                if hasattr(building, 'building_type'):
                    if building.building_type == 'DORMS':
                        self.fields['room_type'].choices = [('DORM', 'Dormitory')]
                    elif building.building_type == 'ROOMS':
                        self.fields['room_type'].choices = [
                            choice for choice in Room.ROOM_TYPES 
                            if choice[0] != 'DORM'
                        ]
                    # If 'BOTH' or no building_type, keep all choices
            except (Building.DoesNotExist, ValueError):
                pass

class ReservationAdminForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = Room.objects.all()
        
        room = None
        initial_room = self.initial.get("room")

        if isinstance(initial_room, int):
            try:
                room = Room.objects.get(pk=initial_room)
            except Room.DoesNotExist:
                room = None
        elif isinstance(initial_room, Room):
            room = initial_room

        if not room and self.instance and self.instance.pk and hasattr(self.instance, "room"):
            room = self.instance.room

        if room:
            today = timezone.now().date()
            future_reservations = room.reservation_set.filter(
                is_cancelled=False,
                check_out_date__gte=today
            ).exclude(id=self.instance.id).order_by('check_in_date')

            if future_reservations.exists():
                first = future_reservations.first()
                self.fields['room'].help_text = (
                    f"⚠️ Room {room.number} is occupied from "
                    f"{first.check_in_date.strftime('%d/%m/%Y')} to {first.check_out_date.strftime('%d/%m/%Y')}."
                )

            self.fields['room'].help_text = (self.fields['room'].help_text or "") + \
                                            f"\nCapacity: {room.capacity} guest(s)"

    def clean(self):
        cleaned_data = super().clean()

        check_in_date = cleaned_data.get("check_in_date")
        check_out_date = cleaned_data.get("check_out_date")
        room = cleaned_data.get("room")
        is_cancelled = cleaned_data.get("is_cancelled")
        guests = cleaned_data.get("guests")

        if not room or not check_in_date or not check_out_date or is_cancelled:
            return cleaned_data

        # Room availability validation
        overlapping_reservations = Reservation.objects.filter(
            room=room,
            is_cancelled=False,
            check_out_date__gt=check_in_date,
            check_in_date__lt=check_out_date
        ).exclude(id=self.instance.pk if self.instance.pk else None)

        if overlapping_reservations.exists():
            raise ValidationError({
                'room': f"Room {room.number} is already occupied during these dates."
            })

        # ✅ Capacity check based on selected guests (no need to touch instance)
        if guests and room and guests.count() > room.capacity:
            raise ValidationError({
                'guests': f"Room capacity exceeded. This room allows {room.capacity} guest(s), "
                        f"but you selected {guests.count()} guest(s)."
            })

        return cleaned_data

    def save(self, commit=True):
        # Save instance first (important to get a valid PK)
        instance = super().save(commit=commit)

        # Store guests data to validate in save_m2m
        self._guests_to_validate = self.cleaned_data.get("guests", [])

        return instance

    def save_m2m(self):
        super().save_m2m()

        guests = self.instance.guests.all()
        room = self.instance.room

        if guests and room:
            if guests.count() > room.capacity:
                raise ValidationError(
                    f"Room capacity exceeded: {room.capacity} guest(s) maximum "
                    f"(trying to assign {guests.count()} guest(s))"
                )

class ImportReservationForm(forms.Form):
    csv_file = forms.FileField(label='CSV File')
