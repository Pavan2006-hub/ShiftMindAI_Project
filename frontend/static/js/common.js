const menuToggle = document.getElementById("menuToggle");
const sidebar = document.getElementById("sidebar");

if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", function (event) {
        event.stopPropagation();
        sidebar.classList.toggle("open");
    });

    // close when a nav link is tapped
    sidebar.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", () => sidebar.classList.remove("open"));
    });

    // close when tapping outside the sidebar
    document.addEventListener("click", function (event) {
        if (sidebar.classList.contains("open") && !sidebar.contains(event.target)) {
            sidebar.classList.remove("open");
        }
    });

    // close on Escape
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            sidebar.classList.remove("open");
        }
    });
}

/* highlight the link whose path best matches the current page */
(function highlightActiveLink() {
    const clean = p => p.replace(/\/$/, "") || "/";
    const currentPath = clean(window.location.pathname);
    let best = null;
    let bestLength = -1;

    document.querySelectorAll(".sidebar .nav-link").forEach(link => {
        const linkPath = clean(link.pathname);
        const matches = currentPath === linkPath || currentPath.startsWith(linkPath + "/");
        if (matches && linkPath.length > bestLength) {
            best = link;
            bestLength = linkPath.length;
        }
    });

    if (best) {
        best.classList.add("active");
    }
})();
document.querySelectorAll(".nav-link").forEach(link => {
    if (link.pathname === window.location.pathname) {
        link.classList.add("active");
    }
});

/* ---------- shared helpers used by every page script ---------- */

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[char]);
}

let csrfToken = null;

async function getCsrfToken(force) {
    if (!csrfToken || force) {
        const response = await fetch("/api/auth/csrf", { credentials: "same-origin" });
        if (!response.ok) {
            throw new Error("Unable to obtain security token.");
        }
        csrfToken = (await response.json()).csrf_token;
    }
    return csrfToken;
}

/* JSON API helper: adds the CSRF header on writes, redirects to /login on 401,
   and throws Error(message) on failures. */
async function api(path, options) {
    options = options || {};
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Accept": "application/json" };

    if (options.body !== undefined) {
        headers["Content-Type"] = "application/json";
    }
    if (method !== "GET") {
        headers["X-CSRFToken"] = await getCsrfToken(false);
    }

    const response = await fetch(path, {
        method: method,
        credentials: "same-origin",
        headers: headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined
    });

    let data = {};
    try { data = await response.json(); } catch (e) { /* non-JSON body */ }

    if (response.status === 401 && !path.startsWith("/api/auth/login")) {
        window.location.href = "/login";
        throw new Error("Please sign in again.");
    }
    if (!response.ok || data.success === false) {
        throw new Error(data.message || "Request failed (" + response.status + ").");
    }
    return data;
}

function badge(value) {
    const text = String(value || "unknown");
    return '<span class="badge ' + escapeHTML(text.toLowerCase()) + '">' +
        escapeHTML(text) + "</span>";
}

function formatDate(iso) {
    if (!iso) { return "-"; }
    const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));   // server stores UTC
    return d.toLocaleString();
}

function showMessage(el, text, type) {
    if (!el) { return; }
    el.className = "alert alert-" + (type || "error");
    el.textContent = text;
    el.hidden = false;
}

const logoutButton = document.getElementById("logoutButton");

if (logoutButton) {
    logoutButton.addEventListener("click", async function () {
        try {
            await api("/api/auth/logout", { method: "POST" });
            window.location.href = "/login";
        } catch (error) {
            alert("Unable to log out. Please try again.");
        }
    });
}
