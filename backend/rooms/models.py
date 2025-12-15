from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.html import format_html

# ----------------------------
# Buildings & Floors
# ----------------------------
class Building(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Floor(models.Model):
    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name="floors"
    )
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, blank=True, null=True)

    # Keep this aligned with Room.ROOM_TYPES codes
    ROOM_TYPE_CHOICES = [
        ("PRIVATE", "Private room"),
        ("MALE_DORM", "Male dormitory"),
        ("FEMALE_DORM", "Female dormitory"),
    ]
    allowed_room_types = models.JSONField(
        default=list,
        help_text="List of allowed room types for this floor (codes: PRIVATE, MALE_DORM, FEMALE_DORM)",
    )

    class Meta:
        unique_together = ("building", "number")
        ordering = ["building", "number"]

    def __str__(self):
        return f"Floor {self.number}"


# ----------------------------
# Rooms
# ----------------------------
class Room(models.Model):
    # Only these three choices
    ROOM_TYPES = [
        ("PRIVATE", "Private room"),
        ("MALE_DORM", "Male dormitory"),
        ("FEMALE_DORM", "Female dormitory"),
    ]

    # Manual toggle (still respected by the helpers below)
    is_available = models.BooleanField(default=True)

    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name="rooms", null=True, blank=True
    )
    floor = models.ForeignKey(
        Floor, on_delete=models.CASCADE, related_name="rooms", null=True, blank=True
    )

    number = models.CharField(max_length=10)

    # Big enough for "FEMALE_DORM"
    room_type = models.CharField(max_length=12, choices=ROOM_TYPES, default="PRIVATE")

    capacity = models.PositiveIntegerField()
    has_fan = models.BooleanField(default=False, verbose_name="Has fan")
    has_attached_bathroom = models.BooleanField(default=False)
    has_kitchen = models.BooleanField(default=False)
    donation_due = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Suggested donation amount for this room",
    )
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

    class Meta:
        verbose_name_plural = "Rooms and Dorms"
        unique_together = ("building", "floor", "number")
        ordering = ["number", "building", "floor"]

    def __str__(self):
        building = self.building.name if self.building else "No Building"
        floor = f"Floor {self.floor.number}" if self.floor else "No Floor"
        return f"#{self.number} ({building} - {floor})"

    # -------- helpers used across admin/dashboard/templates --------
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
        if self.building and self.floor:
            return f"#{self.number} - {self.building.name} - Floor {self.floor.number}"
        return f"#{self.number}"

    def is_currently_available(self):
        """
        Real-time availability:
        - False if manual switch off, needs_repair, or needs_cleaning.
        - False if there is an active (non-cancelled) reservation spanning today.
        - True otherwise.
        """
        today = date.today()
        if not self.is_available or self.needs_repair or self.needs_cleaning:
            return False

        return not self.reservation_set.filter(
            is_cancelled=False, check_in_date__lte=today, check_out_date__gt=today
        ).exists()

    def get_availability_status(self):
        """
        Human-readable status used consistently everywhere.
        """
        today = date.today()

        if not self.is_available:
            return "❌ Unavailable (Manual)"
        if self.needs_repair:
            return "🔧 Unavailable (Repairs)"
        if self.needs_cleaning:
            return "🧹 Needs Cleaning"

        active_reservation = self.reservation_set.filter(
            is_cancelled=False,
            is_checked_in=True,
            check_in_date__lte=today,
            check_out_date__gt=today,
        ).first()
        if active_reservation:
            return "🛌 Occupied"

        available_from = self.get_available_from()
        if isinstance(available_from, date) and available_from > today:
            return f"📅 Available from {available_from.strftime('%b %d, %Y')}"
        return "✅ Available"

    def get_available_from(self):
        """
        Returns the next date the room is free **after** the next blocking reservation.
        """
        today = date.today()

        # If globally unavailable / under repair, we cannot compute a meaningful date
        if not self.is_available or self.needs_repair:
            return "---"

        # Case 1: currently occupied — take the latest active checkout, then add 1 day
        active_qs = self.reservation_set.filter(
            is_cancelled=False, check_in_date__lte=today, check_out_date__gt=today
        ).order_by("check_out_date")
        if active_qs.exists():
            return active_qs.last().check_out_date + timedelta(days=1)

        # Case 2: not occupied now, but there is a future reservation
        future_qs = self.reservation_set.filter(
            is_cancelled=False, check_in_date__gt=today
        ).order_by("check_in_date")
        if future_qs.exists():
            first_upcoming = future_qs.first()
            return first_upcoming.check_out_date + timedelta(days=1)

        # Case 3: no reservations blocking — treat as immediately available
        return "---"

    get_available_from.short_description = "Available From"

    # -------- safety: keep building/floor consistent --------
    def clean(self):
        super().clean()

        # If a floor is selected, force building to match it
        if self.floor and (self.building_id != self.floor.building_id):
            self.building_id = self.floor.building_id

        if self.building and self.floor and self.floor.building_id != self.building_id:
            raise ValidationError("Selected floor doesn't belong to the selected building")

        room_contents = {
            "beds": self.beds or 0,
            "pillows": self.pillows or 0,
            "mats": self.mats or 0,
            "foldable_cots": self.foldable_cots or 0,
            "chairs": self.chairs or 0,
            "stools": self.stools or 0,
        }
        for field, value in room_contents.items():
            if value < 0:
                raise ValidationError(f"{field.replace('_', ' ').title()} cannot be negative")

        if self.capacity is None:
            raise ValidationError("Capacity cannot be null")
        if self.capacity <= 0:
            raise ValidationError("Capacity must be a positive number")

    def save(self, *args, **kwargs):
        if self.floor and (self.building_id != self.floor.building_id):
            self.building_id = self.floor.building_id
        super().save(*args, **kwargs)


# ----------------------------
# Guests & Reservations
# ----------------------------
class Guest(models.Model):
    full_name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    id_document = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Main profile photo (with preview)
    photo = models.ImageField(upload_to="guest_photos/", blank=True, null=True)

    # NEW: document scans (no previews on the form)
    passport_scan = models.ImageField(upload_to="guest_passports/", blank=True, null=True)
    visa_scan = models.ImageField(upload_to="guest_visas/", blank=True, null=True)

    def __str__(self):
        return self.full_name

    # --- admin preview (read-only) for the main photo only ---
    def photo_preview(self):
        if self.photo and hasattr(self.photo, "url"):
            return format_html(
                '<img src="{}" style="max-width:240px;height:auto;border-radius:8px;" />',
                self.photo.url,
            )
        return "—"
    photo_preview.short_description = "Photo preview"

    # Small thumbnail for the admin list view
    def photo_thumb(self):
        if self.photo and hasattr(self.photo, "url"):
            return format_html(
                '<img src="{}" style="width:32px;height:32px;object-fit:cover;border-radius:4px;" />',
                self.photo.url,
            )
        return "—"
    photo_thumb.short_description = "Photo"   # column header


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
    allow_guest_overlap = models.BooleanField(
        default=False,
        help_text="Check this to allow the same guest to have overlapping reservations",
    )

    def __str__(self):
        if not self.pk:
            return "Reservation (unsaved)"
        guest_names = ", ".join(g.full_name for g in self.guests.all())
        return f"Reservation {self.id} for {guest_names} in Room {self.room}"

    def guest_list(self):
        if self.pk:
            return ", ".join(g.full_name for g in self.guests.all())
        return "No guests assigned"
    guest_list.short_description = "Guests"
