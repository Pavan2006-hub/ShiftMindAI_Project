const $ = id => document.getElementById(id);
const id = document.querySelector("[data-incident-id]").dataset.incidentId;
const base = "/api/incidents/" + id;
let me = null;

function msg(t, type) { showMessage($("pageMessage"), t, type); window.scrollTo(0, 0); }

async function load() {
    try {
        const r = (await api(base)).incident;
        $("dTitle").textContent = r.title; $("dService").textContent = r.service_name;
        $("dBadges").innerHTML = badge(r.severity) + " " + badge(r.priority) + " " + badge(r.status);
        const rows = [["Description", r.description], ["Error message", r.error_message], ["System logs", r.system_logs],
            ["Assigned to", r.assigned_engineer ? r.assigned_engineer.name : "Unassigned"],
            ["Verified root cause", r.verified_root_cause], ["Resolution", r.resolution_summary],
            ["Created", formatDate(r.created_at)], ["Resolved", r.resolved_at ? formatDate(r.resolved_at) : "-"]];
        $("dFields").innerHTML = rows.filter(x => x[1]).map(x =>
            "<dt>" + x[0] + '</dt><dd><div class="' + (x[0] === "System logs" ? "pre" : "") + '">' + escapeHTML(x[1]) + "</div></dd>").join("");
        $("statusSelect").value = r.status;
        $("actionList").innerHTML = r.actions.length ? r.actions.map(a => "<li>" + badge(a.outcome) + " " +
            escapeHTML(a.action_description) + (a.actual_result ? " → <em>" + escapeHTML(a.actual_result) + "</em>" : "") +
            "<small>" + escapeHTML(a.engineer_name || "Unknown") + " · " + formatDate(a.created_at) + "</small></li>").join("")
            : '<li class="muted">No actions recorded yet.</li>';
        $("logList").innerHTML = r.logs.slice().reverse().map(l => "<li>" + escapeHTML(l.log_message) +
            "<small>" + escapeHTML(l.log_level) + " · " + formatDate(l.timestamp) + "</small></li>").join("");
        $("analyzeLink").href = "/ai-analysis?incident=" + id;
    } catch (e) { msg(e.message, "error"); }
}

(async function init() {
    try {
        me = (await api("/api/auth/me")).user;
        if (me.role === "admin") $("adminZone").hidden = false;
        (await api("/api/auth/engineers")).data.forEach(u => $("assignSelect").add(new Option(u.name, u.id)));
    } catch (e) { /* non-fatal */ }
    load();
})();

async function act(fn, ok) {
    try { await fn(); msg(ok, "success"); await load(); } catch (e) { msg(e.message, "error"); }
}

$("saveStatus").onclick = () => act(() => api(base + "/status", { method: "PATCH", body: { status: $("statusSelect").value } }), "Status updated.");
$("saveAssign").onclick = () => {
    if (!$("assignSelect").value) return msg("Choose an engineer first.", "error");
    act(() => api(base + "/assign", { method: "POST", body: { engineer_id: parseInt($("assignSelect").value, 10) } }), "Engineer assigned.");
};
$("actionForm").addEventListener("submit", ev => {
    ev.preventDefault();
    const body = { action_description: $("actionDesc").value.trim(), outcome: $("actionOutcome").value };
    if ($("actionResult").value.trim()) body.actual_result = $("actionResult").value.trim();
    act(async () => { await api(base + "/actions", { method: "POST", body: body }); $("actionForm").reset(); }, "Action recorded.");
});
$("resolveBtn").onclick = () => {
    const body = { resolution_summary: $("resSummary").value.trim() };
    if ($("resCause").value.trim()) body.verified_root_cause = $("resCause").value.trim();
    if (!body.resolution_summary) return msg("A resolution summary is required.", "error");
    act(() => api(base + "/resolve", { method: "POST", body: body }), "Incident resolved.");
};
$("deleteBtn").onclick = async () => {
    if (!confirm("Delete this incident permanently?")) return;
    try { await api(base, { method: "DELETE" }); window.location.href = "/incidents"; } catch (e) { msg(e.message, "error"); }
};
