// static/admin/reservation_admin.js
// Hotel-style room reservation form
// Flow: Building → Room → Calendar dates

(function($) {
    $(document).ready(function() {
        var roomSelect = $('#id_room');
        var buildingSelect = $('#id_building');
        var checkInDateInput = $('#id_check_in_date');
        var checkOutDateInput = $('#id_check_out_date');
        
        console.log('✓ Reservation admin script loaded');
        
        /**
         * Update room options based on building selection
         */
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
                        
                        // Try to restore the current selection if it exists
                        if (currentValue) {
                            roomSelect.val(currentValue);
                        }
                        
                        roomSelect.trigger('change');
                        console.log('✓ Updated room options:', data.results.length, 'rooms available');
                    },
                    error: function(xhr, status, error) {
                        console.error('✗ Error loading rooms:', error);
                    }
                });
            } else {
                // Clear room options if no building selected
                roomSelect.empty();
                roomSelect.append(new Option('---------', ''));
                roomSelect.trigger('change');
            }
        }

        /**
         * EVENT: Building selection changes
         * This is the PRIMARY trigger for the hotel-style flow
         */
        buildingSelect.on('change', function() {
            var buildingId = $(this).val();
            console.log('Building selected:', buildingId);
            updateRoomOptions(buildingId);
            // Clear dates when building changes
            checkInDateInput.val('');
            checkOutDateInput.val('');
        });
        
        /**
         * EVENT: Room selection changes
         * Calendar will load in reservation_calendar.js
         */
        roomSelect.on('change', function() {
            console.log('Room selected:', $(this).val());
        });
        
        /**
         * Initialize on page load
         */
        var initialBuildingId = buildingSelect.val();
        if (initialBuildingId) {
            console.log('Initial building found:', initialBuildingId);
            updateRoomOptions(initialBuildingId);
        }
    });
})(django.jQuery);