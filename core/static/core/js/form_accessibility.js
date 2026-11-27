(() => {
    function connectFieldErrors() {
        const errors = Array.from(
            document.querySelectorAll(
                ".auth-field-error, .field-error, .field-errors > span"
            )
        );
        let firstInvalidField = null;

        errors.forEach((error, index) => {
            const group = error.closest(".auth-form-group, .form-group");
            const field = group?.querySelector("input, select, textarea");
            if (!field) return;

            if (!error.id) error.id = `field-error-${index + 1}`;
            error.setAttribute("role", "alert");
            field.setAttribute("aria-invalid", "true");
            const describedBy = new Set(
                (field.getAttribute("aria-describedby") || "")
                    .split(/\s+/)
                    .filter(Boolean)
            );
            describedBy.add(error.id);
            field.setAttribute("aria-describedby", [...describedBy].join(" "));
            firstInvalidField ||= field;
        });

        if (firstInvalidField) {
            firstInvalidField.focus({ preventScroll: false });
            return;
        }

        const summary = document.querySelector(
            ".auth-alert[role='alert'], .form-errors, .form-error"
        );
        if (summary) {
            if (!summary.hasAttribute("tabindex")) summary.tabIndex = -1;
            summary.focus({ preventScroll: false });
        }
    }

    function startLoading(event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.method !== "post") return;
        if (form.dataset.submitting === "true") {
            event.preventDefault();
            return;
        }

        const button = event.submitter || form.querySelector(
            "button[type='submit'], input[type='submit']"
        );
        if (!button) return;

        form.dataset.submitting = "true";
        form.setAttribute("aria-busy", "true");
        button.disabled = true;
        button.setAttribute("aria-busy", "true");

        const status = document.createElement("span");
        status.className = "form-loading-status";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        status.textContent = form.dataset.loadingText || "Submitting…";
        button.insertAdjacentElement("afterend", status);

        if (form.dataset.slowLoadingText) {
            const delay = Number(form.dataset.slowLoadingDelay) || 2500;
            const timer = window.setTimeout(() => {
                if (form.dataset.submitting === "true" && status.isConnected) {
                    status.textContent = form.dataset.slowLoadingText;
                }
            }, delay);
            form.dataset.loadingTimer = String(timer);
        }
    }

    function resetRestoredForms() {
        document.querySelectorAll("form[data-submitting='true']").forEach((form) => {
            const timer = Number(form.dataset.loadingTimer);
            if (timer) window.clearTimeout(timer);
            delete form.dataset.loadingTimer;
            delete form.dataset.submitting;
            form.removeAttribute("aria-busy");
            form.querySelectorAll("button[aria-busy], input[aria-busy]").forEach((button) => {
                button.disabled = false;
                button.removeAttribute("aria-busy");
            });
            form.querySelectorAll(".form-loading-status").forEach((status) => status.remove());
        });
    }

    document.addEventListener("DOMContentLoaded", connectFieldErrors);
    document.addEventListener("submit", startLoading);
    document.addEventListener("click", (event) => {
        const dismissButton = event.target.closest(".message-dismiss");
        dismissButton?.closest(".message")?.remove();
    });
    window.addEventListener("pageshow", resetRestoredForms);
})();
