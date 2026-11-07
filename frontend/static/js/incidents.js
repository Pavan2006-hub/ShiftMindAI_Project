let page = 1, pages = 1, timer = null;
const $ = id => document.getElementById(id);

async function load() {
    const params = new URLSearchParams({ page: page, per_page: 10 });
    ["status", "severity"].forEach(k => { if ($(k).value) params.set(k, $(k).value); });
    if ($("search").value.trim()) params.set("search", $("search").value.trim());
    try {
        const r = await api("/api/incidents?" + params);
        pages = r.pagination.pages || 1;
        $("pageInfo").textContent = "Page " + r.pagination.page + " of " + pages + " (" + r.pagination.total + ")";
        $("prev").disabled = page <= 1; $("next").disabled = page >= pages;
        $("incidentRows").innerHTML = r.data.length ? r.data.map(i =>
            '<tr class="clickable" onclick="location.href=\'/incidents/' + i.id + '\'"><td>' + i.id + "</td><td>" +
            escapeHTML(i.title) + "</td><td>" + escapeHTML(i.service_name) + "</td><td>" + badge(i.severity) +
            "</td><td>" + badge(i.priority) + "</td><td>" + badge(i.status) + "</td><td>" + formatDate(i.created_at) + "</td></tr>").join("")
            : '<tr><td colspan="7" class="empty-state">No incidents match.</td></tr>';
    } catch (e) {
        $("incidentRows").innerHTML = '<tr><td colspan="7" class="empty-state">' + escapeHTML(e.message) + "</td></tr>";
    }
}
["status", "severity"].forEach(k => $(k).addEventListener("change", () => { page = 1; load(); }));
$("search").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 350); });
$("prev").onclick = () => { if (page > 1) { page--; load(); } };
$("next").onclick = () => { if (page < pages) { page++; load(); } };
load();
