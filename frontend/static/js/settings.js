const $ = id => document.getElementById(id);

(async () => {
    try {
        const s = await api("/api/ai/status");
        const pill = (ok, name, extra) => '<p style="margin-bottom:8px"><span class="status-pill ' + (ok ? "ok" : "off") + '">' + (ok ? "Connected" : "Not configured") + "</span> <strong>" + name + "</strong> " + escapeHTML(extra) + "</p>";
        $("integrations").innerHTML = pill(s.groq.configured, "Groq AI", s.groq.model || "") +
            pill(s.hindsight.configured, "Hindsight memory", "bank: " + (s.hindsight.bank_id || ""));
    } catch (e) { $("integrations").textContent = e.message; }
})();

$("pwBtn").onclick = async () => {
    try {
        await api("/api/auth/change-password", { method: "POST", body: { current_password: $("curPass").value, new_password: $("newPass").value } });
        $("curPass").value = ""; $("newPass").value = ""; showMessage($("pwMessage"), "Password updated.", "success");
    } catch (e) { showMessage($("pwMessage"), e.message, "error"); }
};

if ($("engBtn")) $("engBtn").onclick = async () => {
    try {
        await api("/api/auth/register", { method: "POST", body: { name: $("engName").value.trim(), email: $("engEmail").value.trim(), password: $("engPass").value } });
        ["engName", "engEmail", "engPass"].forEach(i => $(i).value = ""); showMessage($("engMessage"), "Engineer account created.", "success");
    } catch (e) { showMessage($("engMessage"), e.message, "error"); }
};
