document.addEventListener("DOMContentLoaded", function () {
    const roomSelect = document.querySelector("#id_room");
    const checkIn = document.querySelector("#id_check_in_date");
    const checkOut = document.querySelector("#id_check_out_date");

    if (!roomSelect || !checkIn || !checkOut) return;

    // Create calendar container
    const calendarContainer = document.createElement("div");
    calendarContainer.id = "reservation-calendar";
    calendarContainer.style.marginTop = "15px";

    roomSelect.closest(".form-row").appendChild(calendarContainer);

    let fp = null;

    function loadCalendar(roomId) {
        if (!roomId) return;

        fetch(`/rooms/room-availability/?room_id=${roomId}`)
            .then(res => res.json())
            .then(data => {
                if (fp) fp.destroy();

                fp = flatpickr(calendarContainer, {
                    inline: true,
                    mode: "range",
                    dateFormat: "Y-m-d",
                    disable: data.booked.map(r => ({
                        from: r.from,
                        to: r.to
                    })),
                    onChange: function (selectedDates) {
                        if (selectedDates.length === 2) {
                            checkIn.value = flatpickr.formatDate(selectedDates[0], "Y-m-d");
                            checkOut.value = flatpickr.formatDate(selectedDates[1], "Y-m-d");
                            
                            // Trigger change events so room dropdown updates
                            $(checkIn).trigger('change');
                            $(checkOut).trigger('change');
                        }
                    }
                });
            });
    }

    // Initial load (edit form)
    if (roomSelect.value) {
        loadCalendar(roomSelect.value);
    }

    // Reload when room changes
    roomSelect.addEventListener("change", function () {
        loadCalendar(this.value);
    });
});