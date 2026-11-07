const $ = id => document.getElementById(id);
const FIELDS = ["active_incidents", "resolved_incidents", "successful_actions", "failed_actions", "verified_findings", "pending_tasks", "recommendations"];

function render(h) {
    $("hoView").innerHTML = '<div class="panel" style="margin-bottom:20px"><div class="panel-header"><div><h3>Handover #' + h.id +
        "</h3><p>" + escapeHTML(h.outgoing_engineer || "-") + " → " + escapeHTML(h.incoming_engineer || "-") + '</p></div><a class="secondary-button small-button" href="/api/handovers/' + h.id + '/pdf">Download PDF</a></div>' +
        '<div class="result-card"><h4>Summary</h4><p>' + escapeHTML(h.summary) + "</p></div>" +
        FIELDS.map(f => '<div class="result-card"><h4>' + f.replace(/_/g, " ").replace(/^./, c => c.toUpperCase()) + "</h4>" +
            ((h[f] || []).length ? "<ul>" + h[f].map(x => "<li>" + escapeHTML(x) + "</li>").join("") + "</ul>" : '<p class="muted">None.</p>') + "</div>").join("") + "</div>";
    window.scrollTo(0, $("hoView").offsetTop - 80);
}

async function loadList() {
    try {
        const r = await api("/api/handovers");
        $("hoRows").innerHTML = r.data.length ? r.data.map(h => "<tr class=\"clickable\" data-id=\"" + h.id + "\"><td>" + h.id + "</td><td>" +
            escapeHTML(h.outgoing_engineer || "-") + "</td><td>" + escapeHTML(h.incoming_engineer || "-") + "</td><td>" + formatDate(h.created_at) +
            "</td><td>View</td></tr>").join("") : '<tr><td colspan="5" class="empty-state">No handovers yet.</td></tr>';
        document.querySelectorAll("#hoRows tr[data-id]").forEach(tr => tr.onclick = async () => {
            try { render((await api("/api/handovers/" + tr.dataset.id)).handover); } catch (e) { showMessage($("hoMessage"), e.message, "error"); }
        });
    } catch (e) { $("hoRows").innerHTML = '<tr><td colspan="5" class="empty-state">' + escapeHTML(e.message) + "</td></tr>"; }
}

(async () => {
    try { (await api("/api/auth/engineers")).data.forEach(u => $("incoming").add(new Option(u.name, u.id))); } catch (e) { /* optional */ }
    loadList();
})();

$("generate").onclick = async () => {
    $("hoMessage").hidden = true; $("generate").disabled = true; $("generate").textContent = "Generating...";
    const body = { shift_hours: parseInt($("hours").value, 10) || 8 };
    if ($("incoming").value) body.incoming_engineer_id = parseInt($("incoming").value, 10);
    if ($("notes").value.trim()) body.notes = $("notes").value.trim();
    try {
        const r = await api("/api/handovers", { method: "POST", body: body });
        showMessage($("hoMessage"), r.handover.ai_generated ? "Handover generated with AI." : "Handover generated (rule-based summary - add GROQ_API_KEY for AI summaries).", "info");
        render(r.handover); loadList();
    } catch (e) { showMessage($("hoMessage"), e.message, "error"); }
    $("generate").disabled = false; $("generate").textContent = "Generate handover";
};
