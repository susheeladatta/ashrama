(function ($) {
    $(document).ready(function () {
        const roomSelect = $("#id_room");
        const checkIn = $("#id_check_in_date");
        const checkOut = $("#id_check_out_date");

        function toggleCalendar() {
            if (roomSelect.val()) {
                checkIn.closest(".form-row").show();
                checkOut.closest(".form-row").show();
            } else {
                checkIn.closest(".form-row").hide();
                checkOut.closest(".form-row").hide();
                checkIn.val("");
                checkOut.val("");
            }
        }

        // Initial state
        toggleCalendar();

        // On room change
        roomSelect.on("change", function () {
            toggleCalendar();
        });
    });
})(django.jQuery);