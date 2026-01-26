(function () {
  function refreshRooms() {
    const buildingSelect = document.getElementById("id_building");
    const roomSelect = document.getElementById("id_room");
    const checkIn = document.getElementById("id_check_in_date");
    const checkOut = document.getElementById("id_check_out_date");

    if (!buildingSelect || !roomSelect) return;

    const building = buildingSelect.value;
    if (!building) return;

    const roomsUrl =
      buildingSelect.dataset.roomsUrl ||
      buildingSelect.getAttribute("data-rooms-url");

    if (!roomsUrl) return;

    const params = new URLSearchParams();
    params.append("building", building);

    if (checkIn && checkIn.value) {
      params.append("check_in_date", checkIn.value);
    }

    if (checkOut && checkOut.value) {
      params.append("check_out_date", checkOut.value);
    }

    // reservation id when editing
    const pathParts = window.location.pathname.split("/");
    const maybeId = pathParts[pathParts.length - 3];
    if (maybeId && !isNaN(maybeId)) {
      params.append("reservation_id", maybeId);
    }

    fetch(`${roomsUrl}?${params.toString()}`)
      .then((r) => r.json())
      .then((data) => {
        roomSelect.innerHTML = "";

        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = "---------";
        roomSelect.appendChild(empty);

        data.results.forEach((room) => {
          const opt = document.createElement("option");
          opt.value = room.id;
          opt.textContent = room.text;

          if (room.occupied) {
            opt.style.color = "#ff6666";
          }

          roomSelect.appendChild(opt);
        });
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    const building = document.getElementById("id_building");
    const checkIn = document.getElementById("id_check_in_date");
    const checkOut = document.getElementById("id_check_out_date");

    if (building) building.addEventListener("change", refreshRooms);
    if (checkIn) checkIn.addEventListener("change", refreshRooms);
    if (checkOut) checkOut.addEventListener("change", refreshRooms);

    // initial load (important when editing)
    setTimeout(refreshRooms, 300);
  });
})();
