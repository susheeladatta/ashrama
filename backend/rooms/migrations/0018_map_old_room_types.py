# rooms/migrations/0018_map_old_room_types.py
from django.db import migrations


def forwards(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    Floor = apps.get_model("rooms", "Floor")

    # Map legacy room_type values to the new set
    mapping = {
        "DORM": "MALE_DORM",
        "SUITE": "PRIVATE",
        "HALL": "PRIVATE",
    }

    # Update room_type codes on existing Room rows
    for old, new in mapping.items():
        Room.objects.filter(room_type=old).update(room_type=new)

    # Update any Floor.allowed_room_types JSON lists that still contain old codes
    for f in Floor.objects.all():
        data = f.allowed_room_types
        if not isinstance(data, list):
            continue
        new_list = [mapping.get(code, code) for code in data]
        if new_list != data:
            f.allowed_room_types = new_list
            f.save(update_fields=["allowed_room_types"])


def backwards(apps, schema_editor):
    # No-op – we don't reintroduce old codes
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("rooms", "0017_alter_floor_allowed_room_types_alter_room_room_type"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
