
document.addEventListener("DOMContentLoaded", async () => {

    const API = "/api/auth";

    // Admin engineer-management endpoint
    const ENGINEER_API = `${API}/admin/engineers`;

    let csrfToken = "";
    let searchTimer = null;

    const getElement = (id) => document.getElementById(id);


    // -----------------------------------------------------
    // MESSAGE HANDLING
    // -----------------------------------------------------

    function showMessage(element, message, isError = false) {

        if (!element) return;

        element.textContent = message;
        element.hidden = false;

        element.classList.toggle("error", isError);
        element.classList.toggle("success", !isError);
    }


    // -----------------------------------------------------
    // CSRF TOKEN
    // -----------------------------------------------------

    async function getCsrfToken() {

        const response = await fetch(`${API}/csrf`, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json"
            }
        });

        const result = await response.json().catch(() => ({
            success: false
        }));

        if (!response.ok || !result.success || !result.csrf_token) {
            throw new Error(
                "Unable to obtain security token. Refresh the page."
            );
        }

        csrfToken = result.csrf_token;

        return csrfToken;
    }


    // -----------------------------------------------------
    // COMMON API REQUEST
    // -----------------------------------------------------

    async function apiRequest(url, options = {}) {

        const method = (options.method || "GET").toUpperCase();

        const headers = {
            "Accept": "application/json",
            ...(options.headers || {})
        };

        if (
            method !== "GET" &&
            method !== "HEAD" &&
            method !== "OPTIONS"
        ) {

            if (!csrfToken) {
                await getCsrfToken();
            }

            headers["Content-Type"] = "application/json";
            headers["X-CSRFToken"] = csrfToken;
        }

        const response = await fetch(url, {
            ...options,
            method,
            headers,
            credentials: "same-origin"
        });

        const result = await response.json().catch(() => ({
            success: false,
            message: "The server returned an invalid response."
        }));

        if (!response.ok || result.success !== true) {

            // Refresh the token if the server reports a CSRF failure.
            if (
                response.status === 400 &&
                /csrf/i.test(result.message || "")
            ) {
                csrfToken = "";
            }

            throw new Error(
                result.message || `Request failed (${response.status}).`
            );
        }

        return result;
    }


    // -----------------------------------------------------
    // LOAD PROFILE
    // -----------------------------------------------------

    async function loadProfile() {

        const message = getElement("profileMessage");

        try {

            const result = await apiRequest(`${API}/me`);

            const user = result.user;

            if (!user) {
                throw new Error("Unable to retrieve user information.");
            }

            if (getElement("profileName")) {
                getElement("profileName").textContent = user.name;
            }

            if (getElement("profileEmail")) {
                getElement("profileEmail").textContent = user.email;
            }

            if (getElement("profileRole")) {
                getElement("profileRole").textContent = user.role;
            }

            if (getElement("profileStatus")) {
                getElement("profileStatus").textContent =
                    user.is_active ? "Active" : "Inactive";
            }

            return user;

        } catch (error) {

            if (getElement("profileName")) {
                getElement("profileName").textContent = "Unavailable";
            }

            showMessage(message, error.message, true);

            console.error("Profile loading error:", error);

            return null;
        }
    }


    // -----------------------------------------------------
    // CHANGE PASSWORD
    // -----------------------------------------------------

    const passwordButton = getElement("pwBtn");

    if (passwordButton) {

        passwordButton.addEventListener("click", async () => {

            const currentPassword = getElement("curPass").value;
            const newPassword = getElement("newPass").value;

            const message = getElement("pwMessage");

            if (!currentPassword || !newPassword) {

                showMessage(
                    message,
                    "Enter your current password and new password.",
                    true
                );

                return;
            }

            const passwordBytes = new TextEncoder().encode(
                newPassword
            ).length;

            if (
                newPassword.length < 8 ||
                passwordBytes > 72
            ) {

                showMessage(
                    message,
                    "New password must contain at least 8 characters and no more than 72 bytes.",
                    true
                );

                return;
            }

            passwordButton.disabled = true;

            try {

                const result = await apiRequest(
                    `${API}/change-password`,
                    {
                        method: "POST",
                        body: JSON.stringify({
                            current_password: currentPassword,
                            new_password: newPassword
                        })
                    }
                );

                showMessage(message, result.message);

                getElement("curPass").value = "";
                getElement("newPass").value = "";

            } catch (error) {

                showMessage(message, error.message, true);

                console.error("Password update error:", error);

            } finally {

                passwordButton.disabled = false;
            }

        });
    }


    // -----------------------------------------------------
    // ADMIN ENGINEER MANAGEMENT
    // -----------------------------------------------------

    const engineerList = getElement("engineerList");
    const engineerSearch = getElement("engineerSearch");
    const engineerMessage = getElement("engineerMessage");


    // -----------------------------------------------------
    // CREATE HTML ELEMENT SAFELY
    // -----------------------------------------------------

    function createTextElement(tag, className, value) {

        const element = document.createElement(tag);

        if (className) {
            element.className = className;
        }

        element.textContent = value ?? "";

        return element;
    }


    // -----------------------------------------------------
    // LOAD AND DISPLAY ENGINEERS
    // -----------------------------------------------------

    async function loadEngineers(search = "") {

        if (!engineerList) return;

        engineerList.textContent = "Loading engineers...";

        try {

            const url =
                `${ENGINEER_API}?search=${encodeURIComponent(search)}`;

            const result = await apiRequest(url);

            engineerList.replaceChildren();

            const engineers = Array.isArray(result.engineers)
                ? result.engineers
                : [];

            if (engineers.length === 0) {

                const emptyMessage = createTextElement(
                    "p",
                    "muted",
                    search
                        ? "No engineers match your search."
                        : "No engineers found. Add an engineer to get started."
                );

                engineerList.appendChild(emptyMessage);

                return;
            }

            // Engineer count
            const count = createTextElement(
                "p",
                "muted",
                `Total engineers: ${engineers.length}`
            );

            count.style.marginBottom = "15px";

            engineerList.appendChild(count);


            // Engineer rows
            engineers.forEach((engineer) => {

                const row = document.createElement("div");

                row.className = "engineer-row";


                // Engineer details
                const details = document.createElement("div");

                details.className = "engineer-details";


                const name = createTextElement(
                    "strong",
                    "",
                    engineer.name
                );

                const email = createTextElement(
                    "p",
                    "",
                    engineer.email
                );


                const status = createTextElement(
                    "span",
                    "status-pill",
                    engineer.is_active ? "Active" : "Inactive"
                );

                status.classList.add(
                    engineer.is_active ? "active" : "inactive"
                );


                details.append(name, email, status);


                // Engineer action buttons
                const actions = document.createElement("div");

                actions.className = "engineer-actions";


                // -----------------------------------------
                // EDIT ENGINEER
                // -----------------------------------------

                const editButton = createTextElement(
                    "button",
                    "secondary-button small-button",
                    "Edit"
                );

                editButton.type = "button";

                editButton.addEventListener("click", async () => {

                    const newName = prompt(
                        "Enter engineer name:",
                        engineer.name
                    );

                    if (newName === null) return;

                    const newEmail = prompt(
                        "Enter engineer email:",
                        engineer.email
                    );

                    if (newEmail === null) return;

                    if (!newName.trim() || !newEmail.trim()) {

                        showMessage(
                            engineerMessage,
                            "Name and email cannot be empty.",
                            true
                        );

                        return;
                    }

                    editButton.disabled = true;

                    try {

                        const updated = await apiRequest(
                            `${ENGINEER_API}/${engineer.id}`,
                            {
                                method: "PATCH",
                                body: JSON.stringify({
                                    name: newName.trim(),
                                    email: newEmail.trim(),
                                    is_active: engineer.is_active
                                })
                            }
                        );

                        showMessage(
                            engineerMessage,
                            updated.message
                        );

                        await loadEngineers(
                            engineerSearch?.value || ""
                        );

                    } catch (error) {

                        showMessage(
                            engineerMessage,
                            error.message,
                            true
                        );

                        console.error("Engineer update error:", error);

                    } finally {

                        editButton.disabled = false;
                    }

                });


                // -----------------------------------------
                // ACTIVATE / DEACTIVATE ENGINEER
                // -----------------------------------------

                const statusButton = createTextElement(
                    "button",
                    "secondary-button small-button",
                    engineer.is_active ? "Deactivate" : "Activate"
                );

                statusButton.type = "button";

                statusButton.addEventListener("click", async () => {

                    const action = engineer.is_active
                        ? "deactivate"
                        : "activate";

                    if (
                        !confirm(
                            `Are you sure you want to ${action} ${engineer.name}?`
                        )
                    ) {
                        return;
                    }

                    statusButton.disabled = true;

                    try {

                        const updated = await apiRequest(
                            `${ENGINEER_API}/${engineer.id}`,
                            {
                                method: "PATCH",
                                body: JSON.stringify({
                                    name: engineer.name,
                                    email: engineer.email,
                                    is_active: !engineer.is_active
                                })
                            }
                        );

                        showMessage(
                            engineerMessage,
                            updated.message
                        );

                        await loadEngineers(
                            engineerSearch?.value || ""
                        );

                    } catch (error) {

                        showMessage(
                            engineerMessage,
                            error.message,
                            true
                        );

                        console.error("Engineer status error:", error);

                    } finally {

                        statusButton.disabled = false;
                    }

                });


                // -----------------------------------------
                // DELETE ENGINEER
                // -----------------------------------------

                const deleteButton = createTextElement(
                    "button",
                    "danger-button small-button",
                    "Delete"
                );

                deleteButton.type = "button";

                deleteButton.addEventListener("click", async () => {

                    if (
                        !confirm(
                            `Permanently delete ${engineer.name}? This cannot be undone.`
                        )
                    ) {
                        return;
                    }

                    deleteButton.disabled = true;

                    try {

                        const deleted = await apiRequest(
                            `${ENGINEER_API}/${engineer.id}`,
                            {
                                method: "DELETE"
                            }
                        );

                        showMessage(
                            engineerMessage,
                            deleted.message
                        );

                        await loadEngineers(
                            engineerSearch?.value || ""
                        );

                    } catch (error) {

                        showMessage(
                            engineerMessage,
                            error.message,
                            true
                        );

                        console.error("Engineer deletion error:", error);

                    } finally {

                        deleteButton.disabled = false;
                    }

                });


                // Add buttons
                actions.append(
                    editButton,
                    statusButton,
                    deleteButton
                );

                row.append(details, actions);

                engineerList.appendChild(row);

            });

        } catch (error) {

            engineerList.replaceChildren();

            const errorMessage = createTextElement(
                "p",
                "alert error",
                error.message
            );

            engineerList.appendChild(errorMessage);

            console.error("Engineer loading error:", error);

            showMessage(
                engineerMessage,
                error.message,
                true
            );
        }
    }


    // -----------------------------------------------------
    // ADD NEW ENGINEER
    // -----------------------------------------------------

    const addEngineerButton = getElement("engBtn");

    if (addEngineerButton) {

        addEngineerButton.addEventListener("click", async () => {

            const name = getElement("engName").value.trim();
            const email = getElement("engEmail").value.trim();
            const password = getElement("engPass").value;

            const message = getElement("engMessage");

            if (!name || !email || !password) {

                showMessage(
                    message,
                    "Enter the engineer name, email and temporary password.",
                    true
                );

                return;
            }

            const passwordBytes = new TextEncoder().encode(
                password
            ).length;

            if (
                password.length < 8 ||
                passwordBytes > 72
            ) {

                showMessage(
                    message,
                    "Password must contain at least 8 characters and no more than 72 bytes.",
                    true
                );

                return;
            }

            addEngineerButton.disabled = true;

            try {

                const result = await apiRequest(
                    ENGINEER_API,
                    {
                        method: "POST",
                        body: JSON.stringify({
                            name,
                            email,
                            password
                        })
                    }
                );

                showMessage(
                    message,
                    result.message
                );

                getElement("engName").value = "";
                getElement("engEmail").value = "";
                getElement("engPass").value = "";

                // Refresh engineer list after creation
                await loadEngineers(
                    engineerSearch?.value || ""
                );

            } catch (error) {

                showMessage(
                    message,
                    error.message,
                    true
                );

                console.error("Engineer creation error:", error);

            } finally {

                addEngineerButton.disabled = false;
            }

        });
    }


    // -----------------------------------------------------
    // SEARCH ENGINEERS
    // -----------------------------------------------------

    if (engineerSearch) {

        engineerSearch.addEventListener("input", () => {

            clearTimeout(searchTimer);

            searchTimer = setTimeout(() => {

                loadEngineers(
                    engineerSearch.value.trim()
                );

            }, 300);

        });
    }


    // -----------------------------------------------------
    // INITIALIZATION
    // -----------------------------------------------------

    try {

        await getCsrfToken();

    } catch (error) {

        console.error("CSRF initialization error:", error);
    }


    // Load logged-in user profile
    const user = await loadProfile();


    // Load engineer list only for admin
    if (
        user &&
        user.role === "admin" &&
        engineerList
    ) {

        await loadEngineers();
    }

});
