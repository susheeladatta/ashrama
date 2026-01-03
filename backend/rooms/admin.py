import nested_admin
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Max, Count, Q, Exists, OuterRef
from django.utils import timezone

from .models import Building, Floor, Room, Guest, Reservation
from .forms import RoomAdminForm, ReservationAdminForm
from .utils import format_room_option


# ---------- Inline forms ----------
class EmptyFloorForm(forms.ModelForm):
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
        return obj._rooms_count


class _HiddenModelAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}


@admin.register(Floor)
class FloorAdmin(_HiddenModelAdmin):
    pass


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
    ]

    list_filter = [
        "building",
        "room_type",
        "has_fan",
        "has_attached_bathroom",
        "has_kitchen",
        "needs_repair",
        "needs_supplies",
    ]

    def get_building_info(self, obj):
        b = obj.building.name if obj.building else ""
        f = obj.floor.number if obj.floor else ""
        return f"{b} – Floor {f}"


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone_number", "email"]


# ---------- Reservation (FINAL, CORRECT FIX) ----------
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    class Media:
        js = ("admin/reservation_admin.js",)

    form = ReservationAdminForm
    filter_horizontal = ("guests",)

    list_display = (
        "__str__",
        "is_checked_in",
        "is_checked_out",
        "is_cancelled",
        "is_paid",
    )

    list_filter = (
        "is_checked_in",
        "is_checked_out",
        "is_cancelled",
        "is_paid",
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        CRITICAL FIX:
        - Exclude rooms that are currently occupied
        - Still allow the current room when editing
        """
        if db_field.name == "room":
            today = timezone.now().date()

            occupied_rooms = Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lte=today,
                check_out_date__gt=today,
            )

            qs = Room.objects.annotate(
                is_occupied_now=Exists(occupied_rooms)
            ).filter(is_occupied_now=False)

            # Allow current room when editing
            object_id = request.resolver_match.kwargs.get("object_id")
            if object_id:
                try:
                    reservation = Reservation.objects.select_related("room").get(pk=object_id)
                    qs = qs | Room.objects.filter(pk=reservation.room_id)
                except Reservation.DoesNotExist:
                    pass

            kwargs["queryset"] = qs.distinct()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if "room" in fields:
            if "building" in fields:
                fields.remove("building")
            idx = fields.index("room")
            fields.insert(idx, "building")
        return fields
