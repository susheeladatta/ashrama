// static/admin/reservation_admin.js
(function () {
    // run after DOM is ready
    function ready(fn) {
        if (document.readyState !== "loading") fn();
        else document.addEventListener("DOMContentLoaded", fn);
    }

    ready(function () {
        // target the admin fields
        var building = document.getElementById("id_building");
        var room = document.getElementById("id_room");

        if (!building || !room) return;

        function clearRooms() {
            // remove all options and add the blank placeholder
            room.innerHTML = "";
            var opt = document.createElement("option");
            opt.value = "";
            opt.textContent = "---------";
            room.appendChild(opt);
        }

        function fetchAndFill(buildingId, keepSelected) {
            clearRooms();
            if (!buildingId) return;

            var url = building.getAttribute("data-rooms-url");
            if (!url) return;

            fetch(url + "?building=" + encodeURIComponent(buildingId), {
                credentials: "same-origin"
            })
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    var current = room.value;
                    if (!data || !data.results) return;
                    data.results.forEach(function (item) {
                        var o = document.createElement("option");
                        o.value = item.id;
                        o.textContent = item.text;
                        room.appendChild(o);
                    });
                    if (keepSelected && current) {
                        // try to restore previously selected value if present
                        try { room.value = current; } catch (e) { /* ignore */ }
                    }
                })
                .catch(function (err) { console.error("Error loading rooms:", err); });
        }

        // initial: if building preselected (editing), fetch rooms for that building
        if (building.value) {
            fetchAndFill(building.value, true);
        } else {
            clearRooms();
        }

        // on building change
        building.addEventListener("change", function () {
            fetchAndFill(building.value, false);
        });
    });
})();
