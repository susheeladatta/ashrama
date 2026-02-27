# admin.py - CLEAN FIXED VERSION
import nested_admin
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import Max, Count, Case, When, Value, BooleanField, Exists, OuterRef

from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html

from .models import Building, Floor, Room, Guest, Reservation
from .forms import RoomAdminForm, ReservationAdminForm

from django.db.models import (
    Case, When, Value, BooleanField,
    Exists, OuterRef
)
from django.utils import timezone


# ---------- Inline forms ----------
class EmptyFloorForm(forms.ModelForm):
    """Render NO visible fields for Floor inside the Building page."""
    class Meta:
        model = Floor
        fields = []


class RoomInline(nested_admin.NestedTabularInline):
    model = Room
    extra = 0
    fields = (
        "number", "room_type", "capacity",
        "has_fan", "has_attached_bathroom", "has_kitchen",
        "donation_due",
        "current_availability",
        "needs_repair", "needs_supplies", "needs_cleaning",
    )
    readonly_fields = ("current_availability",)
    show_change_link = True

    def current_availability(self, obj):
        return obj.get_availability_status()
    current_availability.short_description = "Is available (now)"


class FloorInline(nested_admin.NestedStackedInline):
    model = Floor
    form = EmptyFloorForm
    extra = 0
    inlines = [RoomInline]
    classes = ("collapsible-floor",)


@admin.register(Building)
class BuildingAdmin(nested_admin.NestedModelAdmin):
    list_display = ("name", "description", "total_rooms")
    search_fields = ("name", "description")
    inlines = [FloorInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_rooms_count=Count("rooms"))

    @admin.display(ordering="_rooms_count", description="Rooms")
    def total_rooms(self, obj):
        if hasattr(obj, "_rooms_count"):
            return obj._rooms_count
        return Room.objects.filter(building=obj).count()

    class Media:
        js = ("admin/collapsible_inlines.js",)
        css = {"all": ("admin/collapsible_inlines.css",)}

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in instances:
            if isinstance(obj, Floor):
                if not obj.number:
                    current_max = (
                        Floor.objects.filter(building=form.instance)
                        .aggregate(Max("number"))["number__max"]
                        or 0
                    )
                    obj.number = current_max + 1
                obj.building = form.instance
                obj.save()

            elif isinstance(obj, Room):
                if obj.floor_id and (obj.building_id != obj.floor.building_id):
                    obj.building_id = obj.floor.building_id
                obj.save()

        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


class _HiddenModelAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}


@admin.register(Floor)
class FloorAdmin(_HiddenModelAdmin):
    pass


class RealAvailabilityFilter(SimpleListFilter):
    title = "Availability (now)"
    parameter_name = "is_available_now"

    def lookups(self, request, model_admin):
        return (
            ("1", "Available"),
            ("0", "Occupied"),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        
        _is_available_now = Case(
            When(
                Exists(
                    Reservation.objects.filter(
                        room=OuterRef("pk"),
                        is_cancelled=False,
                        is_checked_out=False,
                        check_in_date__lte=today,
                        check_out_date__gt=today,
                    )
                ),
                then=Value(False),
            ),
            default=Value(True),
            output_field=BooleanField(),
        )
        
        queryset = queryset.annotate(_is_available_now=_is_available_now)

        if self.value() == "1":
            return queryset.filter(_is_available_now=True)
        if self.value() == "0":
            return queryset.filter(_is_available_now=False)
        return queryset


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    form = RoomAdminForm

    list_display = [
        "number",
        "get_building_info",
        "room_type",
        "capacity",
        "has_fan",
        "get_availability_status",
        "has_attached_bathroom",
        "has_kitchen",
        "donation_due",
        "needs_repair",
        "needs_supplies",
        "contents_summary",
    ]

    list_filter = [
        "building",
        "room_type",
        "has_fan",
        "has_attached_bathroom",
        "has_kitchen",
        "needs_repair",
        "needs_supplies",
        RealAvailabilityFilter,
        "is_available",
    ]

    class Media:
        js = ("admin/room_admin.js",)

    def contents_summary(self, obj):
        return obj.get_contents_summary()

    def get_building_info(self, obj):
        b = obj.building.name if obj.building else ""
        f = obj.floor.number if obj.floor else ""
        return f"{b} – Floor {f}"


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ["photo_thumb", "full_name", "phone_number", "email", "country", "city"]


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """
    Hotel-style reservation admin with calendar date picker.
    Users select: Building → Room → Dates (on calendar)
    """
    class Media:
        js = (
            "admin/reservation_admin.js",  # Your existing file (updated)
            "https://cdn.jsdelivr.net/npm/flatpickr",
            "admin/reservation_calendar.js"  # Your existing file (updated)
        )
        css = {
            "all": (
                "admin/css/reservation_actions.css",
                "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css"
            )
        }

    def reservation_title(self, obj):
        guests = ", ".join(g.full_name for g in obj.guests.all())
        room = obj.room

        if room:
            building = room.building.name
            room_no = room.number
            floor_no = room.floor.number if room.floor else "-"
            location = f"{building} (Room {room_no}, Floor {floor_no})"
        else:
            location = "No room assigned"

        return format_html(
            "<strong>{}</strong><br><span style='color:#aaa'>{}</span>",
            guests,
            location
        )

    reservation_title.short_description = "Reservation"

    form = ReservationAdminForm
    filter_horizontal = ("guests",)

    list_display = (
        "reservation_title",
        "check_in_date",
        "check_out_date",
        "is_checked_in",
        "is_checked_out",
        "is_cancelled",
        "is_paid",
        "row_actions",
    )

    list_filter = (
        "is_checked_in",
        "is_checked_out",
        "is_cancelled",
        "is_paid",
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        fields = list(form.base_fields.keys())

        # Remove dates if present
        if "check_in_date" in fields:
            fields.remove("check_in_date")
        if "check_out_date" in fields:
            fields.remove("check_out_date")

        # Reorder: building, room, dates, guests, then others
        new_order = ["building", "room"]
        
        # Add dates back (will be handled by JavaScript)
        new_order.extend(["check_in_date", "check_out_date"])
        
        # Add guests
        if "guests" in fields:
            new_order.append("guests")
            fields.remove("guests")

        # Add remaining fields
        new_order.extend([f for f in fields if f not in new_order])

        form.base_fields = {k: form.base_fields[k] for k in new_order if k in form.base_fields}

        return form

    def row_actions(self, obj):
        checked_in = "✓ In" if obj.is_checked_in else ""
        checked_out = "✓ Out" if obj.is_checked_out else ""
        cancelled = "✗ Cancelled" if obj.is_cancelled else ""
        paid = "✓ Paid" if obj.is_paid else ""

        return format_html(
            "{} {} {} {}",
            checked_in,
            checked_out,
            cancelled,
            paid
        )
    row_actions.short_description = "Status"