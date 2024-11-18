(function () {
    const items = document.querySelectorAll("[data-i18n]");

    for (let i = 0; i < items.length; i++) {
        const translation = chrome.i18n.getMessage(items[i].getAttribute("data-i18n"));
        if (items[i].value === "i18n") {
            items[i].value = translation;
        } else {
            items[i].innerText = translation;
        }
    }
})();