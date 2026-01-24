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


# ---------- Reservation (FINAL FIX) ----------
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
        "row_actions"
    )

    list_filter = (
        "is_checked_in",
        "is_checked_out",
        "is_cancelled",
        "is_paid",
    )

    def get_fields(self, request, obj=None):
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
    
    # ---------- Row action buttons ----------
    def row_actions(self, obj):
        buttons = []

        if not obj.is_checked_in and not obj.is_cancelled:
            buttons.append(self._btn("Check in", "checkin", obj.pk, "#2ecc71"))

        if obj.is_checked_in and not obj.is_checked_out:
            buttons.append(self._btn("Check out", "checkout", obj.pk, "#f39c12"))

        if not obj.is_cancelled:
            buttons.append(self._btn("Cancel", "cancel", obj.pk, "#e74c3c"))

        if not obj.is_paid:
            buttons.append(self._btn("Paid", "paid", obj.pk, "#3498db"))

        return format_html(" ".join(buttons))

    row_actions.short_description = "Actions"

    def _btn(self, label, action, pk, color):
        return format_html(
            '<a class="button" style="background:{};color:white;padding:4px 8px;'
            'border-radius:4px;text-decoration:none" href="{}">{}</a>',
            color,
            f"{pk}/{action}/",
            label,
        )

    # ---------- URLs ----------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:pk>/checkin/", self.admin_site.admin_view(self.checkin)),
            path("<int:pk>/checkout/", self.admin_site.admin_view(self.checkout)),
            path("<int:pk>/cancel/", self.admin_site.admin_view(self.cancel)),
            path("<int:pk>/paid/", self.admin_site.admin_view(self.paid)),
        ]
        return custom + urls

    # ---------- Actions ----------
    def checkin(self, request, pk):
        obj = Reservation.objects.get(pk=pk)
        obj.is_checked_in = True
        obj.save(update_fields=["is_checked_in"])
        messages.success(request, "Reservation checked in.")
        return redirect(request.META.get("HTTP_REFERER"))

    def checkout(self, request, pk):
        obj = Reservation.objects.get(pk=pk)
        obj.is_checked_out = True
        obj.save(update_fields=["is_checked_out"])
        messages.success(request, "Reservation checked out.")
        return redirect(request.META.get("HTTP_REFERER"))

    def cancel(self, request, pk):
        obj = Reservation.objects.get(pk=pk)
        obj.is_cancelled = True
        obj.save(update_fields=["is_cancelled"])
        messages.success(request, "Reservation cancelled.")
        return redirect(request.META.get("HTTP_REFERER"))

    def paid(self, request, pk):
        obj = Reservation.objects.get(pk=pk)
        obj.is_paid = True
        obj.save(update_fields=["is_paid"])
        messages.success(request, "Marked as paid.")
        return redirect(request.META.get("HTTP_REFERER"))