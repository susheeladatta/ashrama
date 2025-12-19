import nested_admin
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Max, Count
#from dal import autocomplete

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


# ---------- Reservation (FIXED) ----------
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    form = ReservationAdminForm
    filter_horizontal = ("guests",)
    
    # Use custom template for debugging
    change_form_template = "D:/ashrama/backend/rooms/reservation/change_form.html"
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Preload the room for the instance
        if obj and hasattr(obj, 'room_id') and obj.room_id:
            try:
                obj.room = Room.objects.select_related('building', 'floor').get(pk=obj.room_id)
            except Room.DoesNotExist:
                pass
        return form

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if "room" in fields:
            if "building" in fields:
                fields.remove("building")
            idx = fields.index("room")
            fields.insert(idx, "building")
        return fields

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        # Preload the reservation with room data
        if object_id:
            try:
                reservation = Reservation.objects.select_related('room__building', 'room__floor').get(pk=object_id)
                extra_context = extra_context or {}
                extra_context['original'] = reservation
            except Reservation.DoesNotExist:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    class Media:
        js = ("admin/reservation_admin.js",)