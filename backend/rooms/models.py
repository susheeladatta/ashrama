from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import date, timedelta

class Building(models.Model):
    BUILDING_TYPES = [
        ('ROOMS', 'Rooms Only'),
        ('DORMS', 'Dormitories Only'),
        ('BOTH', 'Rooms & Dormitories'),
    ]
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    building_type = models.CharField(
        max_length=10,
        choices=BUILDING_TYPES,
        default='BOTH',
        help_text="What types of accommodations this building has"
    )
    
    def __str__(self):
        return self.name

class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, blank=True, null=True)

    ROOM_TYPE_CHOICES = [
        ('PRIVATE', 'Private Room'),
        ('DORM', 'Dormitory'),
        ('SUITE', 'Suite'),
        ('HALL', 'Hall'),
    ]
    allowed_room_types = models.JSONField(
        default=list,
        help_text="List of allowed room types for this floor (e.g. ['PRIVATE', 'DORM'])"
    )
    
    class Meta:
        unique_together = ('building', 'number')
        ordering = ['building', 'number']
    
    def __str__(self):
        return f"{self.building.name} - Floor {self.number} ({self.name})" if self.name else f"{self.building.name} - Floor {self.number}"

class Room(models.Model):
    ROOM_TYPES = [
        ('DORM', 'Dormitory'),
        ('PRIVATE', 'Private Room'),
        ('SUITE', 'Suite'),
        ('HALL', 'Hall'),
    ]
    is_available = models.BooleanField(default=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='rooms', null=True, blank=True)
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='rooms', null=True, blank=True)
    number = models.CharField(max_length=10)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES, default='PRIVATE')
    capacity = models.PositiveIntegerField()
    has_fan = models.BooleanField(default=False, verbose_name="Has fan")  # Changed from has_ac
    has_attached_bathroom = models.BooleanField(default=False)
    has_kitchen = models.BooleanField(default=False)
    donation_due = models.DecimalField(max_digits=8, decimal_places=2, help_text="Suggested donation amount for this room")
    notes = models.TextField(blank=True, null=True, help_text="Special notes about this room")
    needs_repair = models.BooleanField(default=False)
    repair_notes = models.TextField(blank=True, null=True, help_text="Describe what repairs are needed")
    needs_supplies = models.BooleanField(default=False)
    supply_notes = models.TextField(blank=True, null=True, help_text="List of supplies needed")
    needs_cleaning = models.BooleanField(default=False)
    
    # Room contents
    beds = models.PositiveIntegerField(default=1)
    pillows = models.PositiveIntegerField(default=2)
    mats = models.PositiveIntegerField(default=0)
    foldable_cots = models.PositiveIntegerField(default=0)
    chairs = models.PositiveIntegerField(default=2)
    stools = models.PositiveIntegerField(default=0)

    # class Meta:
    #     unique_together = ('building', 'floor', 'number')
    #     ordering = ['number', 'building', 'floor']  # Changed ordering

    class Meta:
        verbose_name_plural = "Rooms and Dorms"
        unique_together = ('building', 'floor', 'number')
        ordering = ['number', 'building', 'floor']
    
    def __str__(self):
        #return f"#{self.number}"  # Simplified to show just room number with #
        # Show: #1 (Gautama Kuteera - Floor 1)
        building = self.building.name if self.building else "No Building"
        floor = f"Floor {self.floor.number}" if self.floor else "No Floor"
        return f"#{self.number} ({building} - {floor})"
    
    # Method to summarize the room contents
    def get_contents_summary(self):
        parts = []
        if self.beds:
            parts.append(f"{self.beds} bed{'s' if self.beds != 1 else ''}")
        if self.pillows:
            parts.append(f"{self.pillows} pillow{'s' if self.pillows != 1 else ''}")
        if self.mats:
            parts.append(f"{self.mats} mat{'s' if self.mats != 1 else ''}")
        if self.foldable_cots:
            parts.append(f"{self.foldable_cots} foldable cot{'s' if self.foldable_cots != 1 else ''}")
        if self.chairs:
            parts.append(f"{self.chairs} chair{'s' if self.chairs != 1 else ''}")
        if self.stools:
            parts.append(f"{self.stools} stool{'s' if self.stools != 1 else ''}")
        return ", ".join(parts) if parts else "No contents listed"
    
    def get_detailed_name(self):
        """Method to get full room details when needed"""
        if self.building and self.floor:
            return f"#{self.number} - {self.building.name} - Floor {self.floor.number}"
        return f"#{self.number}"

    def is_currently_available(self):
        today = date.today()
        if not self.is_available or self.needs_repair or self.needs_cleaning:
            return False
            
        # Available if no overlapping reservations
        return not self.reservation_set.filter(
            is_cancelled=False,
            check_in_date__lte=today,
            check_out_date__gt=today  # Note: gt (not gte) to allow same-day checkin
        ).exists()
        # # Check for active reservations
        # overlapping_reservations = self.reservation_set.filter(
        #     is_cancelled=False,
        #     check_in_date__lte=today,
        #     check_out_date__gte=today
        # )
        # return not overlapping_reservations.exists()

    def get_availability_status(self):
        today = date.today()

        if not self.is_available:
            return "❌ Unavailable (Manual)"
        if self.needs_repair:
            return "🔧 Unavailable (Repairs)"
        if self.needs_cleaning:
            return "🧹 Needs Cleaning"

        # Check for active reservations first
        active_reservation = self.reservation_set.filter(
            is_cancelled=False,
            is_checked_in=True,  # Added this condition
            check_in_date__lte=today,
            check_out_date__gt=today
        ).first()
        
        if active_reservation:
            return "🛌 Occupied"
        
        # Then check for checkout today
        checkout_today = self.reservation_set.filter(
            is_cancelled=False,
            check_out_date=today,
            is_checked_out=False
        ).exists()
        
        if checkout_today:
            return "🚪 Checking Out Today"
        
        # Check future availability
        available_from = self.get_available_from()
        if isinstance(available_from, date) and available_from > today:
            return f"📅 Available from {available_from.strftime('%b %d, %Y')}"
            
        return "✅ Available"

    def get_available_from(self):
        """Returns the next available date considering:
        1. Manual availability flags
        2. Current reservations
        3. Future reservations
        Returns '---' when no reservations exist"""
        today = date.today()
        
        # If manually marked unavailable or needs repair
        if not self.is_available or self.needs_repair:
            return "---"
        
        # Check for active reservations (currently booked)
        active_reservations = self.reservation_set.filter(
            is_cancelled=False,
            check_in_date__lte=today,
            check_out_date__gt=today  # Using gt to exclude checkout day
        )
        
        if active_reservations.exists():
            # Find the next available date after current booking ends
            return active_reservations.first().check_out_date + timedelta(days=1)
        
        # Check for future reservations
        future_reservations = self.reservation_set.filter(
            is_cancelled=False,
            check_in_date__gt=today  # Only future reservations
        ).order_by('check_in_date')  # Get earliest first
        
        if future_reservations.exists():
            return future_reservations.first().check_in_date
        
        # No reservations at all
        return "---"

    get_available_from.short_description = "Available From"


def clean(self):
    super().clean()
    
    # Validate building/floor relationship
    if self.building and self.floor and self.floor.building != self.building:
        raise ValidationError("Selected floor doesn't belong to the selected building")

    
    # Validate room contents - single validation block
    room_contents = {
        'beds': self.beds if self.beds is not None else 0,
        'pillows': self.pillows if self.pillows is not None else 0,
        'mats': self.mats if self.mats is not None else 0,
        'foldable_cots': self.foldable_cots if self.foldable_cots is not None else 0,
        'chairs': self.chairs if self.chairs is not None else 0,
        'stools': self.stools if self.stools is not None else 0
    }
    
    # Check for negative values
    for field, value in room_contents.items():
        if value < 0:
            raise ValidationError(f"{field.replace('_', ' ').title()} cannot be negative")
    
    # Ensure capacity is valid
    if self.capacity is None:
        raise ValidationError("Capacity cannot be null")
    if self.capacity <= 0:
        raise ValidationError("Capacity must be a positive number")

    def get_contents_summary(self):
        """Returns a formatted string of room contents"""
        contents = []
        if self.beds and self.beds > 0:
            contents.append(f"{self.beds} bed(s)")
        if self.pillows and self.pillows > 0:
            contents.append(f"{self.pillows} pillow(s)")
        if self.mats and self.mats > 0:
            contents.append(f"{self.mats} mat(s)")
        if self.foldable_cots and self.foldable_cots > 0:
            contents.append(f"{self.foldable_cots} foldable cot(s)")
        if self.chairs and self.chairs > 0:
            contents.append(f"{self.chairs} chair(s)")
        if self.stools and self.stools > 0:
            contents.append(f"{self.stools} stool(s)")
        return ", ".join(contents) if contents else "No contents listed"
    
    get_contents_summary.short_description = "Room Contents"

class Guest(models.Model):
    full_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    id_document = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.full_name


class Reservation(models.Model):
    guests = models.ManyToManyField("Guest")
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    is_checked_in = models.BooleanField(default=False)
    is_checked_out = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    allow_guest_overlap = models.BooleanField(default=False, 
        help_text="Check this to allow the same guest to have overlapping reservations")

    def __str__(self):
        if not self.pk:
            return "Reservation (unsaved)"
        guest_names = ", ".join(guest.full_name for guest in self.guests.all())
        return f"Reservation {self.id} for {guest_names} in Room {self.room}"

    def guest_list(self):
        if self.pk:
            return ", ".join(guest.full_name for guest in self.guests.all())
        return "No guests assigned"

    guest_list.short_description = "Guests"

def clean(self):
    super().clean()
    
    # Basic validation
    if not self.room:
        raise ValidationError({'room': 'Room is required'})
    
    # Date validation
    if self.check_in_date and self.check_out_date:
        if self.check_in_date >= self.check_out_date:
            raise ValidationError("Check-out date must be after check-in date.")

    # Capacity validation (only if we have a room and guests)
    if hasattr(self, 'guests') and self.room:
        if self.guests.count() > self.room.capacity:
            raise ValidationError(
                f"Room capacity exceeded. The room can accommodate {self.room.capacity} "
                f"guests, but you're trying to add {self.guests.count()}."
            )

    # Skip further validation if essential data is missing
    if not self.check_in_date or not self.check_out_date or not self.room:
        return
    

    # Room availability check (only if not cancelled)
    if not self.is_cancelled:
        overlapping_room = Reservation.objects.filter(
            room=self.room,
            check_in_date__lt=self.check_out_date,
            check_out_date__gt=self.check_in_date,
            is_cancelled=False
        ).exclude(pk=self.pk if self.pk else None)

        if overlapping_room.exists():
            raise ValidationError({
                'room': f"Room {self.room} is already occupied from "
                        f"{overlapping_room.first().check_in_date} to {overlapping_room.first().check_out_date}."
            })

def check_guest_overlaps(self):
    """Check for guest overlaps and return a list of conflicts"""
    if not hasattr(self, 'guests') or self.allow_guest_overlap:
        return []

    conflicts = []
    for guest in self.guests.all():
        overlapping = Reservation.objects.filter(
            guests=guest,
            check_in_date__lt=self.check_out_date,
            check_out_date__gt=self.check_in_date,
            is_cancelled=False
        ).exclude(pk=self.pk)

        if overlapping.exists():
            conflicts.append({
                'guest': guest,
                'reservations': list(overlapping)
            })
    return conflicts

def save(self, *args, **kwargs):
    # Track if this is a check-out transition
    is_new = not self.pk
    was_checked_out = False
    
    if not is_new:
        old_instance = Reservation.objects.get(pk=self.pk)
        was_checked_out = not old_instance.is_checked_out and self.is_checked_out
    
    # First save the instance to ensure we have a PK
    super().save(*args, **kwargs)
    
    # Skip room updates if no room is assigned (defensive programming)
    if not hasattr(self, 'room') or not self.room:
        return
    
    # Handle room status updates
    if self.is_cancelled or self.is_checked_out:
        self.room.is_available = True
        # Only mark for cleaning if this is a new check-out
        if was_checked_out:
            self.room.needs_cleaning = True
    elif self.is_checked_in:
        active_reservations = Reservation.objects.filter(
            room=self.room,
            is_checked_in=True,
            is_checked_out=False,
            is_cancelled=False
        ).exclude(pk=self.pk)
        
        total_checked_in_guests = sum(r.guests.count() for r in active_reservations) + self.guests.count()
        self.room.is_available = total_checked_in_guests < self.room.capacity
        self.room.needs_cleaning = False  # Reset cleaning flag if someone checks in
    
    # Save room only if it exists
    if hasattr(self, 'room') and self.room:
        self.room.save()