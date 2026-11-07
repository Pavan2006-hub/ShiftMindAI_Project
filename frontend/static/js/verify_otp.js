const otpForm = document.getElementById("otpForm");
const otpInput = document.getElementById("otp");
const otpMessage = document.getElementById("otpMessage");
const verifyButton = document.getElementById("verifyButton");
const resendButton = document.getElementById("resendButton");


function showMessage(message, success = false) {
    otpMessage.textContent = message;
    otpMessage.hidden = false;

    otpMessage.classList.toggle("alert-success", success);
    otpMessage.classList.toggle("alert-error", !success);
}


async function getCsrfToken() {
    const response = await fetch("/api/auth/csrf", {
        credentials: "same-origin"
    });

    if (!response.ok) {
        throw new Error("Unable to obtain security token. Refresh the page.");
    }

    const data = await response.json();
    return data.csrf_token;
}


// Verify OTP
otpForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const otp = otpInput.value.trim();

    if (!/^\d{6}$/.test(otp)) {
        showMessage("Please enter a valid six-digit OTP.");
        return;
    }

    verifyButton.disabled = true;
    verifyButton.textContent = "Verifying...";

    try {
        const csrfToken = await getCsrfToken();

        const response = await fetch("/api/auth/verify-otp", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify({ otp: otp })
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            showMessage(result.message || "OTP verification failed.");

            if (response.status === 401 && result.message.includes("expired")) {
                setTimeout(function () {
                    window.location.href = "/login";
                }, 2000);
            }

            return;
        }

        showMessage("Email verified successfully. Redirecting...", true);

        window.location.href = result.redirect || "/dashboard";

    } catch (error) {
        showMessage(error.message);

    } finally {
        verifyButton.disabled = false;
        verifyButton.textContent = "Verify & Sign In";
    }
});


// Resend OTP
resendButton.addEventListener("click", async function () {

    resendButton.disabled = true;
    resendButton.textContent = "Sending...";

    try {
        const csrfToken = await getCsrfToken();

        const response = await fetch("/api/auth/resend-otp", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify({})
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            showMessage(result.message || "Unable to resend OTP.");

            if (result.retry_after) {
                let remaining = result.retry_after;

                resendButton.textContent = `Wait ${remaining}s`;

                const countdown = setInterval(function () {
                    remaining--;

                    if (remaining <= 0) {
                        clearInterval(countdown);
                        resendButton.disabled = false;
                        resendButton.textContent = "Resend OTP";
                    } else {
                        resendButton.textContent = `Wait ${remaining}s`;
                    }
                }, 1000);

                return;
            }

            return;
        }

        showMessage(result.message, true);
        otpInput.value = "";

    } catch (error) {
        showMessage(error.message);

    } finally {
        if (resendButton.textContent === "Sending...") {
            resendButton.disabled = false;
            resendButton.textContent = "Resend OTP";
        }
    }
});