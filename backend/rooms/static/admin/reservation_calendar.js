// static/admin/reservation_calendar.js
// Hotel-style calendar date picker
// Shows available/booked dates for selected room

document.addEventListener("DOMContentLoaded", function () {
    const roomSelect = document.querySelector("#id_room");
    const checkInInput = document.querySelector("#id_check_in_date");
    const checkOutInput = document.querySelector("#id_check_out_date");

    if (!roomSelect || !checkInInput || !checkOutInput) {
        console.warn("Calendar: Required form fields not found");
        return;
    }

    console.log('✓ Calendar script loaded');

    // Create calendar container
    const calendarContainer = document.createElement("div");
    calendarContainer.id = "reservation-calendar";
    calendarContainer.style.marginTop = "15px";
    calendarContainer.style.padding = "15px";
    calendarContainer.style.backgroundColor = "#f9f9f9";
    calendarContainer.style.borderRadius = "4px";
    calendarContainer.style.border = "1px solid #ddd";

    roomSelect.closest(".form-row").insertAdjacentElement("afterend", calendarContainer);

    let fp = null;

    /**
     * Load calendar with availability for selected room
     */
    function loadCalendar(roomId) {
        if (!roomId) {
            console.log("No room selected, calendar hidden");
            if (fp) {
                fp.destroy();
                fp = null;
            }
            calendarContainer.style.display = "none";
            return;
        }

        console.log("Loading calendar for room:", roomId);
        calendarContainer.style.display = "block";

        // Fetch booked dates from backend
        fetch(`/api/room-availability/?room_id=${roomId}`)
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then(data => {
                console.log("Booked dates for room:", data.booked);

                // Destroy existing calendar
                if (fp) {
                    fp.destroy();
                }

                // Clear container
                calendarContainer.innerHTML = "";

                // Initialize flatpickr with date range picker
                fp = flatpickr(calendarContainer, {
                    inline: true,
                    mode: "range",
                    dateFormat: "Y-m-d",
                    minDate: "today",
                    
                    // Disable booked date ranges
                    disable: data.booked.map(range => ({
                        from: new Date(range.from),
                        to: new Date(range.to)
                    })),
                    
                    monthSelectorType: "dropdown",
                    
                    // Custom styling for each day
                    onDayCreate: function(dObj, dStr, fp, dayElem) {
                        // Check if this date is in a booked range
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
                            dayElem.classList.add("booked-date");
                            dayElem.style.backgroundColor = "#ffcccc";
                            dayElem.style.color = "#999";
                            dayElem.style.cursor = "not-allowed";
                            dayElem.style.opacity = "0.6";
                        }
                    },
                    
                    // When user selects dates
                    onChange: function (selectedDates) {
                        if (selectedDates.length === 2) {
                            const checkInDate = flatpickr.formatDate(selectedDates[0], "Y-m-d");
                            const checkOutDate = flatpickr.formatDate(selectedDates[1], "Y-m-d");
                            
                            checkInInput.value = checkInDate;
                            checkOutInput.value = checkOutDate;
                            
                            console.log(`✓ Dates selected: ${checkInDate} to ${checkOutDate}`);
                            
                            // Trigger change events
                            checkInInput.dispatchEvent(new Event('change', { bubbles: true }));
                            checkOutInput.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                });

                console.log("✓ Calendar initialized");
            })
            .catch(error => {
                console.error("✗ Error loading calendar:", error);
                calendarContainer.innerHTML = `<p style="color: red;">Error loading calendar: ${error.message}</p>`;
            });
    }

    /**
     * EVENT: Room selection changes
     * Load calendar for the selected room
     */
    roomSelect.addEventListener("change", function () {
        const roomId = this.value;
        loadCalendar(roomId);
    });

    // Initial load (if editing existing reservation with room selected)
    if (roomSelect.value) {
        console.log("Room already selected (edit mode)");
        loadCalendar(roomSelect.value);
    } else {
        calendarContainer.style.display = "none";
    }
});