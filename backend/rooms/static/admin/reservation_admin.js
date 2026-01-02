// static/admin/reservation_admin.js - UPDATED
(function($) {
    $(document).ready(function() {
        var roomSelect = $('#id_room');
        var buildingSelect = $('#id_building');
        var initialRoomId = roomSelect.val();
        
        // Function to update room options based on building selection
        function updateRoomOptions(buildingId) {
            if (buildingId) {
                $.ajax({
                    url: buildingSelect.data('rooms-url'),
                    data: {
                        'building': buildingId
                    },
                    success: function(data) {
                        var currentValue = roomSelect.val();
                        
                        // Save the current room ID
                        if (!currentValue && initialRoomId) {
                            currentValue = initialRoomId;
                        }
                        
                        roomSelect.empty();
                        
                        // Add the empty option
                        roomSelect.append(new Option('---------', ''));
                        
                        // Add all available rooms
                        $.each(data.results, function(index, item) {
                            var option = new Option(item.text, item.id, false, false);
                            roomSelect.append(option);
                        });
                        
                        // Try to restore the current selection if it exists in the new options
                        if (currentValue) {
                            if (roomSelect.find('option[value="' + currentValue + '"]').length > 0) {
                                roomSelect.val(currentValue);
                            }
                        }
                        
                        roomSelect.trigger('change');
                    },
                    error: function() {
                        console.error('Failed to load rooms for building');
                    }
                });
            } else {
                // Clear room options if no building selected
                roomSelect.empty();
                roomSelect.append(new Option('---------', ''));
                roomSelect.trigger('change');
            }
        }

        // When building selection changes
        buildingSelect.change(function() {
            var buildingId = $(this).val();
            updateRoomOptions(buildingId);
        });

        // Initialize on page load if building is already selected
        var initialBuildingId = buildingSelect.val();
        if (initialBuildingId) {
            updateRoomOptions(initialBuildingId);
        }
        
        // Also check for existing room and ensure it's in the list (for edit mode)
        if (initialRoomId && !roomSelect.find('option[value="' + initialRoomId + '"]').length) {
            // If the current room is not in the dropdown, we need to fetch it
            // This can happen when editing a reservation with an occupied room
            $.ajax({
                url: '/admin/rooms/room/get-room-info/', // You might need to create this endpoint
                data: { 'room_id': initialRoomId },
                success: function(data) {
                    if (data.room) {
                        // Add this room to the dropdown even if it's occupied
                        var option = new Option(data.room.text, data.room.id, true, true);
                        roomSelect.append(option);
                        roomSelect.val(initialRoomId);
                    }
                }
            });
        }
    });
})(django.jQuery);