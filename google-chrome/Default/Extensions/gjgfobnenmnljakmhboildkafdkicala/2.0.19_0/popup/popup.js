addEventListener("DOMContentLoaded", ev => {
	const link = document.getElementById("link");
	const paragraph2 = 	document.getElementById("message");

	const header = document.getElementById("header");
	header.innerText = chrome.i18n.getMessage("appName")

	link.innerText = chrome.i18n.getMessage("deprecationLink");

	paragraph2.innerText = chrome.i18n.getMessage("deprecationMessage");
	paragraph2.appendChild(link);
});