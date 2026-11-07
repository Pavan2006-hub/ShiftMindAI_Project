
const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const loginButton = document.getElementById("loginButton");

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    loginError.hidden = true;
    loginButton.disabled = true;
    loginButton.textContent = "Signing in...";

    try {
        const csrfResponse = await fetch("/api/auth/csrf", {
            credentials: "same-origin"
        });

        if (!csrfResponse.ok) {
            throw new Error("Unable to obtain security token.");
        }

        const csrfData = await csrfResponse.json();

        const response = await fetch("/api/auth/login", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfData.csrf_token
            },
            body: JSON.stringify({
                email: document.getElementById("email").value.trim(),
                password: document.getElementById("password").value
            })
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Login failed.");
        }

        window.location.href = "/dashboard";

    } catch (error) {
        loginError.textContent = error.message;
        loginError.hidden = false;
    } finally {
        loginButton.disabled = false;
        loginButton.textContent = "Sign In";
    }
});
