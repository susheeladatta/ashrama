# admin.py - CLEAN FIXED VERSION
import nested_admin
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import Max, Count, Case, When, Value, BooleanField, Exists, OuterRef

from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html
from django.http import JsonResponse

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


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    class Media:
        js = ("admin/reservation_admin.js",
            "https://cdn.jsdelivr.net/npm/flatpickr",
            "admin/reservation_calendar.js")
        css = {
            "all": ("admin/css/reservation_actions.css",
                    "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css")
        }

        # class Media:
        # css = {
        #     "all": (
        #         "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css",
        #     )
        # }
        # js = (
        #     "https://cdn.jsdelivr.net/npm/flatpickr",
        #     "admin/reservation_calendar.js",
        # )

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

    # -------------------------------------------------
    # FORCE FIELD ORDER
    # guests -> building -> room -> check_in_date -> check_out_date
    # -------------------------------------------------
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        fields = list(form.base_fields.keys())
        ordered_start = ["guests", "building", "room", "check_in_date", "check_out_date"]
        new_fields = [f for f in ordered_start if f in form.base_fields] + [f for f in fields if f not in ordered_start]

        form.base_fields = {k: form.base_fields[k] for k in new_fields}
        return form

    # ---------- Booked dates endpoint for room calendar ----------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("booked-dates/<int:room_id>/", self.admin_site.admin_view(self.booked_dates), name="reservation_booked_dates"),
            path("<int:pk>/checkin/", self.admin_site.admin_view(self.checkin)),
            path("<int:pk>/checkout/", self.admin_site.admin_view(self.checkout)),
            path("<int:pk>/cancel/", self.admin_site.admin_view(self.cancel)),
            path("<int:pk>/paid/", self.admin_site.admin_view(self.paid)),
        ]
        return custom + urls

    def booked_dates(self, request, room_id):
        reservations = Reservation.objects.filter(room_id=room_id).exclude(is_cancelled=True)
        data = []
        for r in reservations:
            if r.check_in_date and r.check_out_date:
                data.append({
                    "from": r.check_in_date.isoformat(),
                    "to": r.check_out_date.isoformat(),
                })
        return JsonResponse(data, safe=False)

    # ---------- Row action buttons ----------
    def row_actions(self, obj):
        buttons = []

        if not obj.is_checked_in and not obj.is_cancelled:
            buttons.append(
                f'<a class="btn-checkin" href="{obj.pk}/checkin/">Check in</a>'
            )

        if obj.is_checked_in and not obj.is_checked_out and not obj.is_cancelled:
            buttons.append(
                f'<a class="btn-checkout" href="{obj.pk}/checkout/">Check out</a>'
            )

        if not obj.is_paid and not obj.is_cancelled:
            buttons.append(
                f'<a class="btn-paid" href="{obj.pk}/paid/">Mark as Paid</a>'
            )

        if not obj.is_cancelled:
            buttons.append(
                f'<a class="btn-cancel" href="{obj.pk}/cancel/">Cancel</a>'
            )

        return format_html(
            '<div class="reservation-actions">{}</div>',
            format_html("".join(buttons))
        )

    row_actions.short_description = "Actions"

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