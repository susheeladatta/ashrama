// static/admin/reservation_admin.js
(function($) {
    $(document).ready(function() {
        // Function to update room options based on building selection
        function updateRoomOptions(buildingId) {
            var roomSelect = $('#id_room');
            var currentRoomId = roomSelect.val();
            
            if (buildingId) {
                $.ajax({
                    url: $('#id_building').data('rooms-url'),
                    data: {
                        'building': buildingId
                    },
                    success: function(data) {
                        roomSelect.empty();
                        $.each(data.results, function(index, item) {
                            var option = new Option(item.text, item.id, false, false);
                            roomSelect.append(option);
                        });
                        
                        // Restore the current room selection if it exists in the new options
                        if (currentRoomId) {
                            roomSelect.val(currentRoomId);
                        }
                        
                        // Trigger change to update UI
                        roomSelect.trigger('change');
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
        $('#id_building').change(function() {
            var buildingId = $(this).val();
            updateRoomOptions(buildingId);
        });

        // Initialize on page load
        var initialBuildingId = $('#id_building').val();
        if (initialBuildingId) {
            updateRoomOptions(initialBuildingId);
        }
        
        // DEBUG: Log the current room value on page load
        console.log('Reservation admin loaded. Room value:', $('#id_room').val());
        console.log('Building value:', $('#id_building').val());
    });
})(django.jQuery);