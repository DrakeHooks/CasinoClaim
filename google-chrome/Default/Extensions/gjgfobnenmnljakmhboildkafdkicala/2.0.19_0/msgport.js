class MessageHostCommunicator {
    constructor() {
        this.retryTimeout = 10000;
        this.applicationName = "com.robin.messagehost";
        this.handler = [];
    }
    onRecieve(message) {
        if (message.f) {
            var handler = this.handler[message.f];
            if (handler) {
                handler(message, response => {
                    if (!response)
                        response = this.defaultResp;
                    response.f = message.f;
                    response._n = message._n;
                    this.msgPort.postMessage(response);
                });
            }
            else if (this.defaultHandler) {
                this.defaultHandler(message, response => {
                    if (!response)
                        response = this.defaultResp;
                    response.f = message.f;
                    response._n = message._n;
                    this.msgPort.postMessage(response);
                });
            }
        }
    }
    setupNativeMessageHost() {
        try {
            this.msgPort = chrome.runtime.connectNative(this.applicationName);
            this.msgPort.onMessage.addListener(m => this.onRecieve(m));
            this.msgPort.onDisconnect.addListener(evt => {
                console.info("Port has been disconnected. " + JSON.stringify(evt));
                setTimeout(() => {
                    this.setupNativeMessageHost();
                    initializeTabs();
                }, this.retryTimeout);
            });
        }
        catch (e) {
            console.warn("Failed to create connection to Robin message host. " + e);
        }
    }
    initializeConnectedPort(port) {
        this.msgPort = port;
        this.msgPort.onMessage.addListener(m => this.onRecieve(m));
        this.msgPort.onDisconnect.addListener(port => console.warn("Message Port has been disconnected. " + port));
    }
    connectToBackgroundScript() {
        try {
            chrome.runtime.onConnect.addListener(port => {
                console.log('Background Script connected.');
                this.initializeConnectedPort(port);
            });
            this.initializeConnectedPort(chrome.runtime.connect());
        }
        catch (e) {
            console.error("Failed to create connection to background page. " + JSON.stringify(e));
        }
    }
    on(functionName, handler) {
        this.handler[functionName] = handler;
    }
    addDefaultHandler(handler) {
        this.defaultHandler = handler;
    }
    post(message) {
        console.log(JSON.stringify(message));
        this.msgPort.postMessage(message);
    }
}
function initializeTabs() {
    chrome.tabs.query({}, function (tabs) {
        for (let tab of tabs) {
            chrome.tabs.sendMessage(tab.id, {});
        }
    });
}
