# rooms/views.py
from datetime import date

from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models.functions import Cast
from django.db.models import IntegerField
from django.views.decorators.http import require_GET

from .models import Room, Building
from .utils import format_room_option


@require_GET
def rooms_for_building(request):
    """
    AJAX endpoint used by the admin JS.
    Expects query param `building` (id). Returns JSON:
      { "results": [ {"id": <pk>, "text": "<label>"}, ... ] }
    """
    building_id = request.GET.get("building")
    if not building_id:
        return JsonResponse({"results": []})

    # verify building exists
    try:
        Building.objects.only("id").get(pk=building_id)
    except Building.DoesNotExist:
        return HttpResponseBadRequest("Invalid building")

    qs = (
        Room.objects.filter(building_id=building_id)
        .select_related("floor")
        .annotate(_num_int=Cast("number", IntegerField()))
        .order_by("floor__number", "_num_int", "number")
    )

    results = [{"id": r.pk, "text": format_room_option(r)} for r in qs]
    return JsonResponse({"results": results})
