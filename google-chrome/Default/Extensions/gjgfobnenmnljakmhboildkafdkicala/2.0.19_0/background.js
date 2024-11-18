var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var forwardPorts = [];
var lastForwardPort;
var lastMsgSeq = 0;
var lastFunc = null;
var communicator = new MessageHostCommunicator();
chrome.runtime.onConnect.addListener(port => {
    if (!port.sender.tab)
        return;
    console.log(`Tab port connected. Id: ${port.sender.tab.id}`);
    setupTabConnection(port, port.sender.tab);
});
chrome.windows.onCreated.addListener(window => {
    console.log(`Window created. WindowId: ${window.id}`);
    communicator.post({ notify: "window_created", wndid: window.id });
});
chrome.windows.onFocusChanged.addListener(windowId => {
    if (windowId !== chrome.windows.WINDOW_ID_NONE) {
        console.log(`Window focused. WindowId: ${windowId}`);
        communicator.post({ notify: "window_focused", wndid: windowId });
    }
});
chrome.windows.onRemoved.addListener(windowId => {
    console.log(`Window removed. WindowId: ${windowId}`);
    communicator.post({ notify: "window_removed", wndid: windowId });
});
chrome.tabs.onActivated.addListener(info => {
    console.log(`Tab activated. Id: ${info.tabId}, WindowId: ${info.windowId}`);
    communicator.post({ notify: "tab_activated", tabid: info.tabId, wndid: info.windowId });
});
chrome.tabs.onAttached.addListener((tabId, info) => {
    console.log(`Tab attached. Id: ${tabId}, WindowId: ${info.newWindowId}`);
    communicator.post({ notify: "tab_attached", tabid: tabId, newwndid: info.newWindowId });
});
chrome.tabs.onDetached.addListener((tabId, info) => {
    console.log(`Tab detached. Id: ${tabId}, Info: ${JSON.stringify(info)}`);
    communicator.post({ notify: "tab_detached", tabid: tabId, oldwndid: info.oldWindowId });
});
chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
    console.log(`Tab updated. Id: ${tabId}, Info: ${JSON.stringify(info)}`);
    communicator.post({ notify: "tab_updated", tabid: tabId, info, tab });
});
chrome.tabs.onRemoved.addListener((tabId, info) => {
    console.log(`Tab removed. Id: ${tabId}, WindowId: ${info.windowId}`);
    communicator.post({ notify: "tab_removed", tabid: tabId, wndid: info.windowId, iswindowclosing: info.isWindowClosing });
});
communicator.on("GetTab", (message, responseFunction) => {
    try {
        chrome.tabs.get(message.arg0, tab => responseFunction(tab));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("GetAllWindows", (message, responseFunction) => {
    try {
        chrome.windows.getAll({ populate: true, windowTypes: ["normal"] }, windows => responseFunction({ windows: windows }));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("GetAllTabs", (message, responseFunction) => {
    try {
        chrome.tabs.query({ windowId: message.arg0 }, tabs => responseFunction({ tabs: tabs }));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("ActivateTab", (message, responseFunction) => {
    try {
        chrome.tabs.update(message.arg0, { active: true }, tab => responseFunction({ tab: tab }));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("RefreshPage", (message, responseFunction) => {
    try {
        var tabId = message.arg0 == -1 ? null : message.arg0;
        chrome.tabs.reload(tabId, { bypassCache: true }, () => responseFunction({}));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("NavigateToUrl", (message, responseFunction) => {
    try {
        var tabId = message.arg1 == -1 ? null : message.arg1;
        chrome.tabs.update(tabId, { url: message.arg0 }, () => responseFunction({}));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("CreateNewTab", (message, responseFunction) => {
    try {
        chrome.tabs.create({ url: message.arg0 }, tab => responseFunction({ id: tab.id, url: tab.url, active: tab.active, title: tab.title }));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("CloseTab", (message, responseFunction) => {
    try {
        chrome.tabs.remove(message.arg0, () => responseFunction({}));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("ClearCookies", (message, responseFunction) => {
    try {
        chrome.browsingData.removeCookies({}, () => responseFunction({}));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("ClearCache", (message, responseFunction) => {
    try {
        chrome.browsingData.removeCache({}, () => responseFunction({}));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e });
    }
});
communicator.on("SetZoom", (message, responseFunction) => {
    try {
        var zoom = message.arg1;
        var tabId = message.arg0 == -1 ? null : message.arg0;
        chrome.tabs.setZoom(tabId, zoom, () => responseFunction({}));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
communicator.on("GetZoom", (message, responseFunction) => {
    try {
        var tabId = message.arg0 == -1 ? null : message.arg0;
        chrome.tabs.getZoom(tabId, zoom => responseFunction({ zoom: zoom }));
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
function sendMessage(newPort, message, responseFunction) {
    lastForwardPort = newPort;
    try {
        lastFunc = message.f;
        lastMsgSeq = message._n;
        newPort.postMessage(message);
    }
    catch (e) {
        responseFunction({ err: "Tab msg post failed" });
    }
}
function setupTabConnection(port, tab) {
    var customPort = port;
    customPort.windowId = tab.windowId;
    customPort.tabId = tab.id;
    forwardPorts[tab.id] = customPort;
    port.onMessage.addListener(message => {
        lastForwardPort = null;
        message.tabId = customPort.tabId;
        message.wndid = customPort.windowId;
        message.url = tab.url;
        message.status = tab.status;
        communicator.post(message);
    });
    port.onDisconnect.addListener(disconnectedPort => {
        console.log(`Tab port disconnected. Id: ${tab.id}`);
        if (lastForwardPort) {
            if (lastFunc == "RunScript") {
                communicator.post({ f: "RunScript", _n: lastMsgSeq, result: "" });
            }
            else {
                communicator.post({ err: `Tab with id ${lastForwardPort.tabId} is no longer available.`, _n: lastMsgSeq });
            }
            lastForwardPort = null;
            lastFunc = null;
        }
        if (forwardPorts[tab.id] == disconnectedPort) {
            console.log("Removing disconnected tab port from registry");
            forwardPorts[tab.id] = null;
            delete forwardPorts[tab.id];
        }
        else {
            console.warn("Disconnected tab port not found in the registry");
        }
    });
    return customPort;
}
function sendInitTab() {
    chrome.windows.getAll({ windowTypes: ["normal"] }, windows => {
        if (windows.length == 1) {
            chrome.tabs.query({}, tabs => tabs.forEach(tab => communicator.post({
                notify: "init_tab",
                tabId: tab.id,
                wndid: tab.windowId,
                url: tab.url,
                status: tab.status
            })));
            console.log("Tab initialized: OK");
        }
    });
}
function asyncWrap(callback) {
    return new Promise((resolve, reject) => {
        try {
            callback(resolve);
        }
        catch (error) {
            reject(error);
        }
    });
}
function injectScriptAsync(tabId, details) {
    return asyncWrap(resolve => {
        chrome.tabs.executeScript(tabId, details, (r) => {
            resolve(r);
        });
    });
}
function getTabAsync(tabId) {
    return asyncWrap(resolve => {
        chrome.tabs.get(tabId, (tab) => {
            resolve(tab);
        });
    });
}
function injectContentScript(tabId) {
    return __awaiter(this, void 0, void 0, function* () {
        try {
            yield injectScriptAsync(tabId, { file: 'msgport.js' });
            yield injectScriptAsync(tabId, { file: 'content.js' });
        }
        catch (e) {
            console.warn('Failed to inject content script: ' + e);
        }
    });
}
communicator.addDefaultHandler((message, responseFunction) => __awaiter(this, void 0, void 0, function* () {
    const port = forwardPorts[message.tabid];
    if (!port) {
        console.warn('Tab id \'' + message.tabid + '\' not found. Trying to manually connect...');
        const tabId = +message.tabid;
        yield injectContentScript(tabId);
        try {
            var tab = yield getTabAsync(tabId);
            let newPort = setupTabConnection(chrome.tabs.connect(tabId, null), tab);
            if (newPort) {
                sendMessage(newPort, message, responseFunction);
            }
            else {
                responseFunction({ err: "Tab id does not exist" });
            }
        }
        catch (error) {
            console.warn('Tab id \'' + message.tabid + '\' does not exist.');
            responseFunction({ err: "Tab id does not exist (setupTabConnection failed)" });
        }
    }
    else {
        sendMessage(port, message, responseFunction);
    }
}));
communicator.setupNativeMessageHost();
try {
    communicator.post({ notify: "plugin_init" });
    console.log("Background Script: OK");
    sendInitTab();
}
catch (e) {
    console.error("Post 'plugin_init' message failed: " + e);
}
