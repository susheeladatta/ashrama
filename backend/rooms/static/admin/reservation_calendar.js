document.addEventListener('DOMContentLoaded', function () {
    const buildingSelect = document.getElementById('id_building');
    const roomSelect = document.getElementById('id_room');
    const calendarContainer = document.getElementById('calendar-container');
    const inlineCalendar = document.getElementById('inline-calendar');
    const checkInDateInput = document.getElementById('id_check_in_date');
    const checkOutDateInput = document.getElementById('id_check_out_date');

    let calendar = null;

    // Initially, hide room select until a building is chosen
    const roomRow = roomSelect.closest('.form-row');
    roomRow.style.display = 'none';

    buildingSelect.addEventListener('change', function () {
        // Show room select when a building is selected
        if (buildingSelect.value) {
            roomRow.style.display = '';
        } else {
            roomRow.style.display = 'none';
        }
        // Also hide calendar when building changes
        calendarContainer.style.display = 'none';
    });

    // Trigger change on load if a building is already selected
    if (buildingSelect.value) {
        buildingSelect.dispatchEvent(new Event('change'));
    }

    roomSelect.addEventListener('change', function () {
        const roomId = this.value;

        if (roomId) {
            // Fetch booked dates for the selected room
            fetch(`/admin/core/reservation/booked-dates/${roomId}/`)
                .then(response => response.json())
                .then(bookedDates => {
                    calendarContainer.style.display = 'block';

                    // Destroy previous calendar instance if it exists
                    if (calendar) {
                        calendar.destroy();
                    }

                    // Initialize flatpickr calendar
                    calendar = flatpickr(inlineCalendar, {
                        mode: 'range',
                        inline: true,
                        dateFormat: 'Y-m-d',
                        disable: bookedDates,
                        onChange: function (selectedDates) {
                            if (selectedDates.length === 2) {
                                // Populate check-in and check-out fields
                                checkInDateInput.value = selectedDates[0].toISOString().split('T')[0];
                                checkOutDateInput.value = selectedDates[1].toISOString().split('T')[0];
                            }
                        }
                    });
                });
        } else {
            calendarContainer.style.display = 'none';
        }
    });

    // If a room is already selected on page load, trigger the change event
    if (roomSelect.value) {
        roomSelect.dispatchEvent(new Event('change'));
    }
});