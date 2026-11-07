const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const loginButton = document.getElementById("loginButton");

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    loginError.hidden = true;
    loginButton.disabled = true;
    loginButton.textContent = "Verifying credentials...";

    try {
        const csrfResponse = await fetch("/api/auth/csrf", {
            credentials: "same-origin"
        });

        if (!csrfResponse.ok) {
            throw new Error("Unable to obtain security token. Refresh the page.");
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

        if (result.otp_required) {
            window.location.href = result.redirect || "/verify-otp";
            return;
        }

        throw new Error("Unexpected login response.");

    } catch (error) {
        loginError.textContent = error.message;
        loginError.hidden = false;
    } finally {
        loginButton.disabled = false;
        loginButton.textContent = "Sign In";
    }
});