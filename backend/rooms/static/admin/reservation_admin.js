// static/admin/reservation_admin.js
(function($) {
    $(document).ready(function() {
        var roomSelect = $('#id_room');
        var buildingSelect = $('#id_building');
        
        // Function to update room options based on building selection
        function updateRoomOptions(buildingId) {
            if (buildingId) {
                var data = {
                    'building': buildingId
                };
                
                // Check if we're editing an existing reservation
                var path = window.location.pathname;
                var match = path.match(/\/change\/(\d+)\//);
                if (match) {
                    data.reservation_id = match[1];
                }
                
                $.ajax({
                    url: buildingSelect.data('rooms-url'),
                    data: data,
                    success: function(data) {
                        var currentValue = roomSelect.val();
                        
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
                            roomSelect.val(currentValue);
                        }
                        
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
        buildingSelect.change(function() {
            var buildingId = $(this).val();
            updateRoomOptions(buildingId);
        });

        // Initialize on page load if building is already selected
        var initialBuildingId = buildingSelect.val();
        if (initialBuildingId) {
            updateRoomOptions(initialBuildingId);
        }
    });
})(django.jQuery);