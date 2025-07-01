(function($) {
    $(document).ready(function() {
        function updateRoomTypeChoices() {
            var floorSelect = $('#id_floor');
            var roomTypeSelect = $('#id_room_type');
            var floorId = floorSelect.val();
            if (!floorId) {
                roomTypeSelect.find('option').show();
                return;
            }
            // You need to make allowedRoomTypes available as a global JS object
            var allowed = window.allowedRoomTypesForFloors ? window.allowedRoomTypesForFloors[floorId] : null;
            if (allowed) {
                roomTypeSelect.find('option').each(function() {
                    var val = $(this).attr('value');
                    if (allowed.indexOf(val) === -1 && val !== "") {
                        $(this).hide();
                    } else {
                        $(this).show();
                    }
                });
            } else {
                roomTypeSelect.find('option').show();
            }
        }
        $('#id_floor').change(updateRoomTypeChoices);
        updateRoomTypeChoices();
    });
})(django.jQuery);
