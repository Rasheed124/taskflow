(() => {
    const menu = document.querySelector("[data-mobile-navigation]");
    if (!(menu instanceof HTMLDetailsElement)) return;

    document.addEventListener("pointerdown", (event) => {
        if (menu.open && !menu.contains(event.target)) {
            menu.open = false;
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || !menu.open) return;

        menu.open = false;
        menu.querySelector("summary")?.focus();
    });
})();
