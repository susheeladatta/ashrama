from django.contrib import admin
from django.shortcuts import render
from django.urls import reverse
from django.db.models import Q, Exists, OuterRef, Count
from django.utils import timezone

from .models import Dashboard
from rooms.models import Building, Room, Reservation


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    change_list_template = "admin/dashboard.html"

    def has_add_permission(self, request): 
        return False
    
    def has_change_permission(self, request, obj=None): 
        return False
    
    def has_delete_permission(self, request, obj=None): 
        return False

    def changelist_view(self, request, extra_context=None):
        today = timezone.localdate()
        
        # Define room type constants
        TYPE_PRIVATE = "PRIVATE"
        TYPE_FEMALE = "FEMALE_DORM"
        TYPE_MALE = "MALE_DORM"
        
        # Subquery to check for active reservations
        active_reservation = Exists(
            Reservation.objects.filter(
                room=OuterRef("pk"),
                is_cancelled=False,
                check_in_date__lte=today,
                check_out_date__gt=today,
            )
        )
        
        items = []
        for b in Building.objects.all().order_by("name"):
            # Get all rooms for this building
            rooms = Room.objects.filter(building=b)
            
            # Create querysets for each room type
            priv = rooms.filter(room_type=TYPE_PRIVATE)
            female = rooms.filter(room_type=TYPE_FEMALE)
            male = rooms.filter(room_type=TYPE_MALE)
            
            # Count private rooms that are actually available (not under repair/cleaning AND not reserved)
            priv_available_count = priv.filter(
                is_available=True,
                needs_repair=False,
                needs_cleaning=False
            ).exclude(
                # Exclude rooms with active reservations
                pk__in=Reservation.objects.filter(
                    room__in=priv,
                    is_cancelled=False,
                    check_in_date__lte=today,
                    check_out_date__gt=today,
                ).values('room_id')
            ).count()
            
            priv_occupied_count = priv.count() - priv_available_count
            
            # Count female dorm rooms that are actually available
            female_available_count = female.filter(
                is_available=True,
                needs_repair=False,
                needs_cleaning=False
            ).exclude(
                pk__in=Reservation.objects.filter(
                    room__in=female,
                    is_cancelled=False,
                    check_in_date__lte=today,
                    check_out_date__gt=today,
                ).values('room_id')
            ).count()
            
            female_occupied_count = female.count() - female_available_count
            
            # Count male dorm rooms that are actually available
            male_available_count = male.filter(
                is_available=True,
                needs_repair=False,
                needs_cleaning=False
            ).exclude(
                pk__in=Reservation.objects.filter(
                    room__in=male,
                    is_cancelled=False,
                    check_in_date__lte=today,
                    check_out_date__gt=today,
                ).values('room_id')
            ).count()
            
            male_occupied_count = male.count() - male_available_count
            
            row = {
                "building": b,
                "building_url": reverse("admin:rooms_building_change", args=[b.id]),
                "total": rooms.count(),
                "total_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}",
                # Private rooms
                "priv_avail": priv_available_count,
                "priv_avail_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_PRIVATE}&is_available__exact=1",
                "priv_occ": priv_occupied_count,
                "priv_occ_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_PRIVATE}&is_available__exact=0",
                # Female dorm
                "female_avail": female_available_count,
                "female_avail_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_FEMALE}&is_available__exact=1",
                "female_occ": female_occupied_count,
                "female_occ_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_FEMALE}&is_available__exact=0",
                # Male dorm
                "male_avail": male_available_count,
                "male_avail_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_MALE}&is_available__exact=1",
                "male_occ": male_occupied_count,
                "male_occ_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&room_type__exact={TYPE_MALE}&is_available__exact=0",
                # Need repair
                "repair": rooms.filter(needs_repair=True).count(),
                "repair_url": f"{reverse('admin:rooms_room_changelist')}?building__id__exact={b.id}&needs_repair__exact=1",
            }
            items.append(row)

        context = {
            "title": "Dashboard",
            "items": items,
            **self.admin_site.each_context(request),
        }
        return render(request, "admin/dashboard.html", context)