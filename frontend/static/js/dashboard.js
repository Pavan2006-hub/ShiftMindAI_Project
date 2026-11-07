
document.addEventListener("DOMContentLoaded", loadDashboard);

async function loadDashboard() {
    const tbody = document.getElementById("recentIncidents");

    try {
        const [stats, list] = await Promise.all([
            api("/api/incidents/stats"),
            api("/api/incidents?page=1&per_page=5")
        ]);

        document.getElementById("totalIncidents").textContent = stats.stats.total;
        document.getElementById("activeIncidents").textContent = stats.stats.active;
        document.getElementById("resolvedIncidents").textContent = stats.stats.resolved;
        document.getElementById("criticalIncidents").textContent = stats.stats.critical;

        const incidents = list.data || [];

        if (!incidents.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state">' +
                "No incidents have been recorded yet.</td></tr>";
            return;
        }

        tbody.innerHTML = incidents.map(i =>
            '<tr class="clickable" onclick="location.href=\'/incidents/' + i.id + '\'">' +
            "<td>" + escapeHTML(i.title) + "</td>" +
            "<td>" + escapeHTML(i.service_name) + "</td>" +
            "<td>" + badge(i.severity) + "</td>" +
            "<td>" + badge(i.status) + "</td></tr>").join("");

    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="empty-state">' +
            escapeHTML(error.message) + "</td></tr>";
    }
}
