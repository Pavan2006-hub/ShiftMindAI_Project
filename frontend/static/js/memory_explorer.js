const $ = id => document.getElementById(id);

(async () => {
    try {
        const s = await api("/api/ai/status");
        if (!s.hindsight.configured) showMessage($("memStatus"), "Hindsight is not configured. Add HINDSIGHT_API_KEY to .env and restart to enable memory.", "info");
    } catch (e) { /* ignore */ }
})();

async function run(kind) {
    const q = $("memQuery").value.trim();
    $("memStatus").hidden = true;
    if (!q) return showMessage($("memStatus"), "Enter a search or question.", "error");
    $("memOutput").innerHTML = '<p class="muted">Working...</p>';
    try {
        if (kind === "search") {
            const r = await api("/api/memory/search", { method: "POST", body: { query: q } });
            $("memOutput").innerHTML = r.data.length ? r.data.map(m => '<div class="result-card"><p>' + escapeHTML(m.text) + "</p>" +
                (m.type ? '<small class="muted">' + escapeHTML(m.type) + "</small>" : "") + "</div>").join("") : '<p class="muted">No memories found.</p>';
        } else {
            const r = await api("/api/memory/reflect", { method: "POST", body: { query: q } });
            $("memOutput").innerHTML = '<div class="result-card"><h4>Answer from memory</h4><p style="white-space:pre-wrap">' + escapeHTML(r.answer || "No answer.") + "</p></div>";
        }
    } catch (e) { $("memOutput").innerHTML = ""; showMessage($("memStatus"), e.message, "error"); }
}
$("searchBtn").onclick = () => run("search");
$("reflectBtn").onclick = () => run("reflect");
$("memQuery").addEventListener("keydown", ev => { if (ev.key === "Enter") run("search"); });
$("noteBtn").onclick = async () => {
    const text = $("noteText").value.trim();
    if (!text) return;
    try { await api("/api/memory/retain", { method: "POST", body: { content: text } }); $("noteText").value = ""; showMessage($("memStatus"), "Saved to memory.", "success"); }
    catch (e) { showMessage($("memStatus"), e.message, "error"); }
};
