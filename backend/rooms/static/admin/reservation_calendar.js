// static/admin/reservation_calendar.js
document.addEventListener("DOMContentLoaded", function () {
    const roomSelect = document.querySelector("#id_room");
    const checkIn = document.querySelector("#id_check_in_date");
    const checkOut = document.querySelector("#id_check_out_date");

    if (!roomSelect || !checkIn || !checkOut) return;

    // Create calendar container with dark Django style
    const calendarContainer = document.createElement("div");
    calendarContainer.id = "reservation-calendar";
    calendarContainer.style.marginTop = "15px";
    calendarContainer.style.padding = "15px";
    calendarContainer.style.backgroundColor = "#333333";
    calendarContainer.style.borderRadius = "4px";
    calendarContainer.style.border = "1px solid #555555";

    roomSelect.closest(".form-row").insertAdjacentElement("afterend", calendarContainer);

    let fp = null;

    function loadCalendar(roomId) {
        if (!roomId) {
            calendarContainer.style.display = "none";
            return;
        }

        calendarContainer.style.display = "block";

        fetch(`/api/room-availability/?room_id=${roomId}`)
            .then(res => res.json())
            .then(data => {
                if (fp) fp.destroy();

                calendarContainer.innerHTML = "";

                fp = flatpickr(calendarContainer, {
                    inline: true,
                    mode: "range",
                    dateFormat: "Y-m-d",
                    minDate: "today",
                    disable: data.booked.map(r => ({
                        from: new Date(r.from),
                        to: new Date(r.to)
                    })),
                    onChange: function (selectedDates) {
                        if (selectedDates.length === 2) {
                            checkIn.value = flatpickr.formatDate(selectedDates[0], "Y-m-d");
                            checkOut.value = flatpickr.formatDate(selectedDates[1], "Y-m-d");
                        }
                    },
                    onDayCreate: function(dObj, dStr, fp, dayElem) {
                        // Mark booked dates with red background
                        let isBooked = false;
                        for (let range of data.booked) {
                            const fromDate = new Date(range.from);
                            const toDate = new Date(range.to);
                            if (dayElem.dateObj >= fromDate && dayElem.dateObj < toDate) {
                                isBooked = true;
                                break;
                            }
                        }
                        
                        if (isBooked) {
                            dayElem.style.backgroundColor = "#8B0000";
                            dayElem.style.color = "#cccccc";
                        }
                    }
                });

                // Apply dark theme styling
                const calendarEl = document.querySelector("#reservation-calendar .flatpickr-calendar");
                if (calendarEl) {
                    calendarEl.style.backgroundColor = "#333333";
                    calendarEl.style.color = "#ffffff";
                    calendarEl.style.borderColor = "#555555";
                }

                const monthEl = document.querySelector("#reservation-calendar .flatpickr-months");
                if (monthEl) {
                    monthEl.style.backgroundColor = "#222222";
                    monthEl.style.color = "#ffffff";
                    monthEl.style.borderColor = "#555555";
                }

                const daysEl = document.querySelector("#reservation-calendar .flatpickr-days");
                if (daysEl) {
                    daysEl.style.backgroundColor = "#333333";
                }

                // Style day elements
                const dayElements = document.querySelectorAll("#reservation-calendar .flatpickr-day");
                dayElements.forEach(day => {
                    day.style.color = "#ffffff";
                    if (!day.classList.contains("booked-date")) {
                        day.addEventListener("mouseover", function() {
                            if (!day.classList.contains("disabled")) {
                                day.style.backgroundColor = "#555555";
                            }
                        });
                        day.addEventListener("mouseout", function() {
                            if (!day.classList.contains("selected") && !day.classList.contains("inRange")) {
                                day.style.backgroundColor = "transparent";
                            }
                        });
                    }
                });

                // Style selected/range dates
                const selectedDays = document.querySelectorAll("#reservation-calendar .flatpickr-day.selected, #reservation-calendar .flatpickr-day.inRange");
                selectedDays.forEach(day => {
                    day.style.backgroundColor = "#0066cc";
                    day.style.color = "#ffffff";
                });
            })
            .catch(error => {
                console.error("Error loading calendar:", error);
                calendarContainer.innerHTML = "<p style='color: #ff6666;'>Error loading calendar</p>";
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