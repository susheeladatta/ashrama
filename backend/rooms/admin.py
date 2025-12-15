import nested_admin
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Max, Count
from dal import autocomplete

from .models import Building, Floor, Room, Guest, Reservation
from .forms import RoomAdminForm, ReservationAdminForm

from django.db.models import (
    Case, When, Value, BooleanField, Q,
    Exists, OuterRef
)
from django.utils import timezone


# ---------- Autocomplete for Floor (DAL) ----------
class FloorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Floor.objects.all()
        building_id = self.forwarded.get("building")
        if building_id:
            qs = qs.filter(building_id=building_id)
        return qs


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
        "current_availability",   # computed, read-only
        "needs_repair", "needs_supplies", "needs_cleaning",
    )
    readonly_fields = ("current_availability",)
    show_change_link = True

    def current_availability(self, obj):
        # Real-time, derived from reservations
        return obj.get_availability_status()
    current_availability.short_description = "Is available (now)"


class FloorInline(nested_admin.NestedStackedInline):
    """Show only the Floor header; rooms remain fully editable underneath."""
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
        # Fast count of related rooms
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
        """
        - Auto-number floors created via the inline (since the field is hidden)
        - Keep Room.building in sync with Room.floor
        """
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


# ---------- Hide Floor in the left menu, keep usable in inlines ----------
class _HiddenModelAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}

@admin.register(Floor)
class FloorAdmin(_HiddenModelAdmin):
    pass


# ---------- Real-time Availability filter (sidebar) ----------
class RealAvailabilityFilter(SimpleListFilter):
    title = "Real-time availability"
    parameter_name = "rt_available"

    def lookups(self, request, model_admin):
        return (("1", "Available"), ("0", "Unavailable"))

    def queryset(self, request, queryset):
        today = timezone.now().date()
        occupied_now = Exists(
            Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lte=today,
                check_out_date__gt=today,
            )
        )
        is_available_now = Case(
            When(occupied_now, then=Value(False)),
            default=Value(True),
            output_field=BooleanField(),
        )
        queryset = queryset.annotate(_is_available_now=is_available_now)

        val = self.value()
        if val == "1":
            return queryset.filter(_is_available_now=True)
        if val == "0":
            return queryset.filter(_is_available_now=False)
        return queryset


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    form = RoomAdminForm

    list_display = [
        "number",
        "get_building_info",           # sortable by building name
        "room_type",
        "capacity",
        "has_fan",
        "get_availability_status",     # real-time availability (sortable)
        "has_attached_bathroom",
        "has_kitchen",
        "donation_due",
        "needs_repair",
        "needs_supplies",
        "contents_summary",
    ]
    list_display_links = ["number"]

    # Sidebar filters
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

    search_fields = ["number", "building__name", "floor__number"]

    fieldsets = (
        ("Location", {"fields": ("building", "floor")}),
        ("Basic", {"fields": ("number", "room_type", "capacity", "donation_due", "is_available")}),
        ("Facilities", {"fields": ("has_fan", "has_attached_bathroom", "has_kitchen")}),
        ("Maintenance", {"fields": ("needs_repair", "repair_notes", "needs_supplies", "supply_notes", "needs_cleaning")}),
        ("Room Contents", {"fields": ("beds", "pillows", "mats", "foldable_cots", "chairs", "stools")}),
        ("Notes", {"fields": ("notes",)}),
    )

    class Media:
        js = ("admin/room_admin.js",)

    def contents_summary(self, obj):
        return obj.get_contents_summary()
    contents_summary.short_description = "Room Contents"

    @admin.display(ordering="_is_available_now", description="Availability")
    def get_availability_status(self, obj):
        return obj.get_availability_status()

    def get_building_info(self, obj):
        b = obj.building.name if obj.building else ""
        f = obj.floor.number if obj.floor else ""
        return f"{b} – Floor {f}"
    get_building_info.short_description = "Building – Floor"
    get_building_info.admin_order_field = "building__name"

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("building", "floor")
            .prefetch_related("reservation_set")
        )

        today = timezone.now().date()
        occupied_now = Exists(
            Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                is_checked_out=False,
                check_in_date__lte=today,
                check_out_date__gt=today,
            )
        )
        is_available_now = Case(
            When(occupied_now, then=Value(False)),
            default=Value(True),
            output_field=BooleanField(),
        )

        return qs.annotate(_is_available_now=is_available_now)


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    # thumbnail first
    list_display = ["photo_thumb", "full_name", "phone_number", "email", "country", "city"]
    search_fields = ["full_name", "phone_number", "email", "country", "city"]
    readonly_fields = ("photo_preview",)

    # Form fields order (only the main photo has a preview)
    fields = (
        "full_name",
        ("country", "city"),
        ("phone_number", "email"),
        "id_document",
        "notes",
        "photo",          # profile photo upload
        "photo_preview",  # read-only preview (main photo only)
        "passport_scan",  # NEW: no preview
        "visa_scan",      # NEW: no preview
    )


# Re-register Reservation with custom form
try:
    admin.site.unregister(Reservation)
except admin.sites.NotRegistered:
    pass


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    class Media:
        js = ("admin/reservation_admin.js",)

    form = ReservationAdminForm
    filter_horizontal = ("guests",)

    def get_fields(self, request, obj=None):
        """
        Insert the helper 'building' directly before 'room'
        so the order is: ... Building, Room, ...
        """
        fields = list(super().get_fields(request, obj))
        if "room" in fields:
            if "building" in fields:
                fields.remove("building")
            idx = fields.index("room")
            fields.insert(idx, "building")
        else:
            if "building" not in fields:
                fields.append("building")
        return fields
