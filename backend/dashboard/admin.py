from django.contrib import admin
from django.shortcuts import render
from django.urls import reverse

from .models import Dashboard
from rooms.models import Building, Room


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    # We render a custom template that lives in:
    # dashboard/templates/admin/dashboard.html
    change_list_template = "admin/dashboard.html"

    # This is a “virtual” model; hide add/edit/delete in the admin
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def changelist_view(self, request, extra_context=None):
        items = []

        # If your internal values are different, edit these three strings:
        TYPE_PRIVATE = "PRIVATE"
        TYPE_FEMALE  = "FEMALE_DORM"
        TYPE_MALE    = "MALE_DORM"

        for b in Building.objects.all().order_by("name"):
            qs = Room.objects.filter(building=b)
            total = qs.count()

            priv   = qs.filter(room_type=TYPE_PRIVATE)
            female = qs.filter(room_type=TYPE_FEMALE)
            male   = qs.filter(room_type=TYPE_MALE)

            row = {
                "building": b,
                "building_url": reverse("admin:rooms_building_change", args=[b.id]),
                "total": total,
                "total_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}",
                # Private
                "priv_avail":     priv.filter(is_available=True).count(),
                "priv_avail_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_PRIVATE}&is_available__exact=1",
                "priv_occ":       priv.filter(is_available=False).count(),
                "priv_occ_url":   f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_PRIVATE}&is_available__exact=0",
                # Female dorm
                "female_avail":     female.filter(is_available=True).count(),
                "female_avail_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_FEMALE}&is_available__exact=1",
                "female_occ":       female.filter(is_available=False).count(),
                "female_occ_url":   f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_FEMALE}&is_available__exact=0",
                # Male dorm
                "male_avail":     male.filter(is_available=True).count(),
                "male_avail_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_MALE}&is_available__exact=1",
                "male_occ":       male.filter(is_available=False).count(),
                "male_occ_url":   f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_MALE}&is_available__exact=0",
                # Need repair
                "repair":     qs.filter(needs_repair=True).count(),
                "repair_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&needs_repair__exact=1",
            }
            items.append(row)

        context = {
            "title": "Dashboard",
            "items": items,
            **self.admin_site.each_context(request),
        }
        return render(request, "admin/dashboard.html", context)
