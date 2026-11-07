const $ = id => document.getElementById(id);

function list(items) { return items && items.length ? "<ul>" + items.map(i => "<li>" + escapeHTML(i) + "</li>").join("") + "</ul>" : '<p class="muted">None.</p>'; }

(async function init() {
    try {
        const r = await api("/api/incidents?per_page=100");
        r.data.forEach(i => $("incidentSelect").add(new Option("#" + i.id + " " + i.title + " [" + i.status + "]", i.id)));
        const pre = new URLSearchParams(location.search).get("incident");
        if (pre) $("incidentSelect").value = pre;
    } catch (e) { showMessage($("aiMessage"), e.message, "error"); }
})();

$("analyzeBtn").onclick = async () => {
    const incidentId = parseInt($("incidentSelect").value, 10);
    $("aiMessage").hidden = true; $("analysisOutput").innerHTML = "";
    if (!incidentId) return showMessage($("aiMessage"), "Select an incident first.", "error");
    $("analyzeBtn").disabled = true; $("analyzeBtn").textContent = "Analyzing...";
    try {
        const r = await api("/api/ai/analyze", { method: "POST", body: { incident_id: incidentId } });
        const a = r.analysis;
        $("analysisOutput").innerHTML =
            '<div class="result-card"><h4>Summary</h4><p>' + escapeHTML(a.summary) + "</p></div>" +
            '<div class="result-card"><h4>Probable causes (unverified)</h4>' + (a.probable_causes.length ? a.probable_causes.map(c =>
                "<p><strong>" + escapeHTML(c.cause) + "</strong> " + badge(c.likelihood) + "<br>" + escapeHTML(c.reasoning) + "</p>").join("") : '<p class="muted">None.</p>') + "</div>" +
            '<div class="result-card"><h4>Recommended steps</h4>' + list(a.recommended_steps) + "</div>" +
            '<div class="result-card"><h4>Things to verify</h4>' + list(a.things_to_verify) + "</div>" +
            '<div class="result-card"><h4>Escalation</h4><p>' + escapeHTML(a.escalation_advice || "-") + "</p></div>" +
            (r.memories_used.length ? '<div class="result-card"><h4>Past memory used</h4>' + list(r.memories_used.map(m => m.text)) + "</div>" : "") +
            '<p class="muted">' + escapeHTML(r.disclaimer) + "</p>";
    } catch (e) { showMessage($("aiMessage"), e.message, "error"); }
    $("analyzeBtn").disabled = false; $("analyzeBtn").textContent = "✧ Analyze";
};
