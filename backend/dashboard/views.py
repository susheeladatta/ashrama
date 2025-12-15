# dashboard/views.py  (or wherever your dashboard view lives)
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rooms.models import Building, Room, Reservation

def dashboard_view(request):
    today = timezone.localdate()

    active_res = Reservation.objects.filter(
        room=OuterRef("pk"),
        is_cancelled=False,
    ).filter(
        Q(is_checked_in=True, is_checked_out=False) |
        Q(check_in_date__lte=today, check_out_date__gt=today)
    )

    rows = []
    for b in Building.objects.all().order_by("name"):
        rooms = Room.objects.filter(building=b).annotate(occupied=Exists(active_res))

        def cnt(rt, occ):
            return rooms.filter(room_type=rt, occupied=occ).count()

        total = rooms.count()

        data = {
            "building": b,
            "total": total,
            "avail_private": cnt(Room.RoomType.PRIVATE, False),
            "occ_private": cnt(Room.RoomType.PRIVATE, True),
            "avail_female": cnt(Room.RoomType.FEMALE_DORM, False),
            "occ_female": cnt(Room.RoomType.FEMALE_DORM, True),
            "avail_male": cnt(Room.RoomType.MALE_DORM, False),
            "occ_male": cnt(Room.RoomType.MALE_DORM, True),
            "need_repair": rooms.filter(needs_repair=True).count(),
        }
        rows.append(data)

    return render(request, "admin/dashboard/dashboard.html", {"rows": rows})
