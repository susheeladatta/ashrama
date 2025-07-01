from rest_framework import serializers
from .models import Room, Building, Floor, Guest, Reservation

class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = '__all__'

class FloorSerializer(serializers.ModelSerializer):
    building = BuildingSerializer()
    class Meta:
        model = Floor
        fields = '__all__'

# class RoomSerializer(serializers.ModelSerializer):
#     building = BuildingSerializer()
#     floor = FloorSerializer()
#     class Meta:
#         model = Room
#         fields = '__all__'

class RoomSerializer(serializers.ModelSerializer):
    building = serializers.PrimaryKeyRelatedField(queryset=Building.objects.all())
    floor = serializers.PrimaryKeyRelatedField(queryset=Floor.objects.all())
    class Meta:
        model = Room
        fields = '__all__'

class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = '__all__'

class ReservationSerializer(serializers.ModelSerializer):
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.all())
    guests = serializers.PrimaryKeyRelatedField(queryset=Guest.objects.all(), many=True)
    class Meta:
        model = Reservation
        fields = '__all__'
