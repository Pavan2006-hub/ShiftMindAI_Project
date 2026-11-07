const $ = id => document.getElementById(id);
let sessionId = null;

function bubble(text, who) {
    const d = document.createElement("div");
    d.className = "bubble " + who; d.textContent = text;
    $("chatMessages").appendChild(d); $("chatMessages").scrollTop = 1e9;
}

async function loadSessions() {
    try {
        const r = await api("/api/ai/chat/sessions");
        $("sessionList").innerHTML = "";
        r.data.forEach(s => {
            const b = document.createElement("button");
            b.textContent = s.preview; b.className = s.id === sessionId ? "active" : "";
            b.onclick = () => openSession(s.id); $("sessionList").appendChild(b);
        });
    } catch (e) { /* ignore */ }
}

async function openSession(id) {
    try {
        const r = await api("/api/ai/chat/sessions/" + id);
        sessionId = id; $("chatMessages").innerHTML = "";
        r.data.forEach(m => { bubble(m.message, "user"); if (m.response) bubble(m.response, "ai"); });
        loadSessions();
    } catch (e) { showMessage($("chatMessage"), e.message, "error"); }
}

$("newChat").onclick = () => { sessionId = null; $("chatMessages").innerHTML = ""; bubble("New chat started. How can I help?", "ai"); loadSessions(); };

async function send() {
    const text = $("chatText").value.trim();
    if (!text) return;
    $("chatMessage").hidden = true; bubble(text, "user"); $("chatText").value = ""; $("chatSend").disabled = true;
    try {
        const r = await api("/api/ai/chat", { method: "POST", body: { message: text, session_id: sessionId } });
        sessionId = r.session_id; bubble(r.reply, "ai"); loadSessions();
    } catch (e) { showMessage($("chatMessage"), e.message, "error"); }
    $("chatSend").disabled = false;
}
$("chatForm").addEventListener("submit", ev => { ev.preventDefault(); send(); });
$("chatText").addEventListener("keydown", ev => { if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(); } });
loadSessions();
