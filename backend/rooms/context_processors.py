from .models import Room

def rooms_needing_repair(request):
    if request.path.startswith('/admin/'):
        rooms = Room.objects.filter(needs_repair=True).select_related('building', 'floor')
        return {
            'rooms_needing_repair': rooms
        }
    return {}