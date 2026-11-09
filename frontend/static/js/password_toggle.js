document.addEventListener("DOMContentLoaded", function () {

    const toggleButtons = document.querySelectorAll(
        "[data-password-toggle]"
    );

    toggleButtons.forEach(function (button) {

        const wrapper = button.closest(".password-input-wrap");
        const passwordField = wrapper.querySelector(
            "[data-password-field]"
        );

        if (!passwordField) return;

        button.addEventListener("click", function () {

            const isPassword =
                passwordField.type === "password";

            passwordField.type = isPassword ? "text" : "password";

            button.setAttribute(
                "aria-pressed",
                String(isPassword)
            );

            button.setAttribute(
                "aria-label",
                isPassword ? "Hide password" : "Show password"
            );

        });

    });

});
