// static/admin/reservation_admin.js
(function($) {
    $(document).ready(function() {
        var roomSelect = $('#id_room');
        var buildingSelect = $('#id_building');
        var checkInDateInput = $('#id_check_in_date');
        var checkOutDateInput = $('#id_check_out_date');
        
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
                            
                            // If room is occupied, disable the option (but still show it)
                            if (item.occupied && String(item.id) !== String(currentValue)) {
                                option.disabled = true;
                                $(option).addClass('occupied-room');
                            }
                        });
                        
                        // Try to restore the current selection if it exists in the new options
                        if (currentValue) {
                            roomSelect.val(currentValue);
                        }
                        
                        roomSelect.trigger('change');
                        
                        console.log('Updated room options:', data.results.length, 'rooms loaded');
                    },
                    error: function(xhr, status, error) {
                        console.error('Error loading rooms:', error);
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
        
        // When check-in or check-out dates change, update room options if building is selected
        checkInDateInput.change(function() {
            var buildingId = buildingSelect.val();
            if (buildingId) {
                updateRoomOptions(buildingId);
            }
        });
        
        checkOutDateInput.change(function() {
            var buildingId = buildingSelect.val();
            if (buildingId) {
                updateRoomOptions(buildingId);
            }
        });
        
        // Also trigger on date input blur (when user finishes typing)
        checkInDateInput.blur(function() {
            var buildingId = buildingSelect.val();
            if (buildingId && checkInDateInput.val() && checkOutDateInput.val()) {
                updateRoomOptions(buildingId);
            }
        });
        
        checkOutDateInput.blur(function() {
            var buildingId = buildingSelect.val();
            if (buildingId && checkInDateInput.val() && checkOutDateInput.val()) {
                updateRoomOptions(buildingId);
            }
        });

        // Initialize on page load if building is already selected
        var initialBuildingId = buildingSelect.val();
        if (initialBuildingId) {
            updateRoomOptions(initialBuildingId);
        }
        
        // Also trigger update when page loads if dates are already filled
        setTimeout(function() {
            var initialBuildingId = buildingSelect.val();
            var checkInDate = checkInDateInput.val();
            var checkOutDate = checkOutDateInput.val();
            
            if (initialBuildingId && checkInDate && checkOutDate) {
                updateRoomOptions(initialBuildingId);
            }
        }, 500);
    });
})(django.jQuery);