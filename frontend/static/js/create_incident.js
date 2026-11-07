const $ = id => document.getElementById(id);

(async function loadEngineers() {
    try {
        const r = await api("/api/auth/engineers");
        r.data.forEach(u => $("assigned").add(new Option(u.name + " (" + u.role + ")", u.id)));
    } catch (e) { /* assignment is optional */ }
})();

$("incidentForm").addEventListener("submit", async ev => {
    ev.preventDefault();
    $("formMessage").hidden = true; $("submitBtn").disabled = true;
    const body = {
        title: $("title").value.trim(), service_name: $("service_name").value.trim(),
        description: $("description").value.trim(), severity: $("severity").value, priority: $("priority").value
    };
    if ($("error_message").value.trim()) body.error_message = $("error_message").value.trim();
    if ($("system_logs").value.trim()) body.system_logs = $("system_logs").value.trim();
    if ($("assigned").value) body.assigned_engineer_id = parseInt($("assigned").value, 10);
    try {
        const r = await api("/api/incidents", { method: "POST", body: body });
        window.location.href = "/incidents/" + r.incident.id;
    } catch (e) {
        showMessage($("formMessage"), e.message, "error");
        $("submitBtn").disabled = false;
    }
});
