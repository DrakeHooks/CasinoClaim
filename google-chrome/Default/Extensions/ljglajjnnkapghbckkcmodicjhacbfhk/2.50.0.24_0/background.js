(() => {
    "use strict";
    var __webpack_modules__ = {
        17967: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.sanitizeUrl = void 0;
            var invalidProtocolRegex = /^([^\w]*)(javascript|data|vbscript)/im, htmlEntitiesRegex = /&#(\w+)(^\w|;)?/g, htmlCtrlEntityRegex = /&(newline|tab);/gi, ctrlCharactersRegex = /[\u0000-\u001F\u007F-\u009F\u2000-\u200D\uFEFF]/gim, urlSchemeRegex = /^.+(:|&colon;)/gim, relativeFirstCharacters = [ ".", "/" ];
            exports.sanitizeUrl = function(url) {
                var str, sanitizedUrl = (str = url || "", str.replace(htmlEntitiesRegex, (function(match, dec) {
                    return String.fromCharCode(dec);
                }))).replace(htmlCtrlEntityRegex, "").replace(ctrlCharactersRegex, "").trim();
                if (!sanitizedUrl) return "about:blank";
                if (function(url) {
                    return relativeFirstCharacters.indexOf(url[0]) > -1;
                }(sanitizedUrl)) return sanitizedUrl;
                var urlSchemeParseResults = sanitizedUrl.match(urlSchemeRegex);
                if (!urlSchemeParseResults) return sanitizedUrl;
                var urlScheme = urlSchemeParseResults[0];
                return invalidProtocolRegex.test(urlScheme) ? "about:blank" : sanitizedUrl;
            };
        },
        88069: function(__unused_webpack_module, exports, __webpack_require__) {
            this && this.__awaiter;
            Object.defineProperty(exports, "__esModule", {
                value: !0
            });
            const communicator_to_native_host_1 = __webpack_require__(89530), background_v1_1 = __webpack_require__(75664), background_v2_1 = __webpack_require__(34968), background_v3_1 = __webpack_require__(56549), logger_1 = __webpack_require__(88901), negotiationFailedError_1 = (__webpack_require__(92025), 
            __webpack_require__(50063));
            logger_1.Logger.enable();
            let backgroundScript;
            const communicator = new communicator_to_native_host_1.CommunicatorToNativeHost;
            communicator.on("LoadScriptsRequest", (request => {
                const loadRequest = request.parameters;
                try {
                    return checkScriptVersion(loadRequest.backgroundVersion, 3, "Background"), checkScriptVersion(loadRequest.contentVersion, 1, "Content"), 
                    checkScriptVersion(loadRequest.apiVersion, 3, "API"), null == backgroundScript || backgroundScript.dispose(), 
                    1 === loadRequest.backgroundVersion && (backgroundScript = new background_v1_1.BackgroundV1(communicator, loadRequest.contentVersion, loadRequest.apiVersion)), 
                    2 === loadRequest.backgroundVersion && (backgroundScript = new background_v2_1.BackgroundV2(communicator, loadRequest.contentVersion, loadRequest.apiVersion)), 
                    3 === loadRequest.backgroundVersion && (backgroundScript = new background_v3_1.BackgroundV3(communicator, loadRequest.contentVersion, loadRequest.apiVersion)), 
                    !0;
                } finally {
                    logger_1.Logger.groupEnd(), (null == loadRequest ? void 0 : loadRequest.isDebugEnabled) || logger_1.Logger.disable();
                }
                function checkScriptVersion(requestedVersion, maxSupportedVersion, scriptName) {
                    if (requestedVersion > maxSupportedVersion) {
                        const errorMessage = `${scriptName} script V${requestedVersion} is not supported`;
                        throw logger_1.Logger.error(`${errorMessage}. Please update your extension.`), new negotiationFailedError_1.NegotiationFailedError(errorMessage);
                    }
                    logger_1.Logger.log(`${scriptName} script V${requestedVersion} exists`);
                }
            })), chrome.runtime.onStartup.addListener((() => logger_1.Logger.log("Startup event"))), 
            communicator.connect(), logger_1.Logger.log("Background base script loaded");
        },
        89530: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.CommunicatorToNativeHost = void 0;
            const communicator_1 = __webpack_require__(84248);
            class CommunicatorToNativeHost extends communicator_1.Communicator {
                constructor() {
                    super(...arguments), this.retryTimeout = 1e4, this.applicationName = "com.microsoft.pad.messagehost";
                }
                connectImpl() {
                    return chrome.runtime.connectNative(this.applicationName);
                }
                onDisconnect(port) {
                    super.onDisconnect(port), setTimeout((() => {
                        this.connect();
                    }), this.retryTimeout);
                }
            }
            exports.CommunicatorToNativeHost = CommunicatorToNativeHost;
        },
        84248: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Communicator = void 0;
            const response_1 = __webpack_require__(74374), logger_1 = __webpack_require__(88901), responseError_1 = __webpack_require__(99669);
            exports.Communicator = class {
                constructor() {
                    this.handler = {}, this.GENERAL_EXCEPTION_CODE = 3;
                }
                on(functionName, handler) {
                    this.handler[functionName] = handler;
                }
                removeHandler(name) {
                    delete this.handler[name];
                }
                addDefaultHandler(handler) {
                    this.defaultHandler = handler;
                }
                post(request) {
                    logger_1.Logger.log("===> Sending message: ", request), this.msgPort.postMessage(request);
                }
                connect() {
                    try {
                        this.initializeConnectedPort(this.connectImpl());
                    } catch (e) {
                        logger_1.Logger.warn("Connection to port failed:", e);
                    }
                }
                onConnect(port) {
                    this.initializeConnectedPort(port);
                }
                initializeConnectedPort(port) {
                    this.msgPort = port;
                    const script = this;
                    this.msgPort.onMessage.addListener((m => __awaiter(this, void 0, void 0, (function*() {
                        return script.onMessageReceived(m);
                    })))), this.msgPort.onDisconnect.addListener((p => script.onDisconnect(p)));
                }
                onDisconnect(port) {
                    logger_1.Logger.warn(`Message Port has been disconnected. ${port}`);
                }
                onMessageReceived(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (void 0 !== request) return logger_1.Logger.groupLoggingAsync((() => __awaiter(this, void 0, void 0, (function*() {
                            var _a;
                            let handler = this.handler[request.name];
                            void 0 === handler && (logger_1.Logger.log("~ Request:", request.requestId, request.name, " using default handler"), 
                            handler = this.defaultHandler);
                            try {
                                let result = handler(request);
                                if (void 0 === result && (result = new response_1.Response(request, !0)), null === result) return logger_1.Logger.log("+ Response to:", request.requestId, "===> :", result), 
                                void this.msgPort.postMessage(new response_1.Response(request, null));
                                if (void 0 !== result.then && "function" == typeof result.then && (result = yield result), 
                                (null == result ? void 0 : result.requestId) === request.requestId) return logger_1.Logger.log("+ Response to:", request.requestId, "===> :", result), 
                                void this.msgPort.postMessage(result);
                                logger_1.Logger.log("+ Response to:", request.requestId, "===> :", result), this.msgPort.postMessage(new response_1.Response(request, result));
                            } catch (e) {
                                logger_1.Logger.error("- Error to:", request.requestId, "===> :", e), this.msgPort.postMessage(new response_1.Response(request, void 0, new responseError_1.ExceptionError(e.name, null !== (_a = e.errorCode) && void 0 !== _a ? _a : this.GENERAL_EXCEPTION_CODE, e.message, e.stack)));
                            }
                        }))), "Received request:", request.requestId, request.name, "=>", request.parameters, "Full:", request);
                    }));
                }
            };
        },
        28230: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Frame = void 0;
            __webpack_require__(87555);
            class Frame {
                constructor(init) {
                    Object.assign(this, init);
                }
                isMain() {
                    return this.id === Frame.MainFrame;
                }
                isAt(ordinal) {
                    var _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        try {
                            return (yield chrome.scripting.executeScript({
                                target: {
                                    tabId: this.tabId,
                                    frameIds: [ null !== (_b = this.id) && void 0 !== _b ? _b : 0 ]
                                },
                                args: [ ordinal ],
                                func: i => window.parent !== window && null !== window.parent && window.parent.frames.length > i && window.parent.frames[i] === window
                            }))[0].result;
                        } catch (_c) {
                            return !1;
                        }
                    }));
                }
            }
            exports.Frame = Frame, Frame.ordinalTimeout = 500, Frame.MainFrame = 0;
        },
        50063: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.NegotiationFailedError = void 0;
            class NegotiationFailedError extends Error {
                constructor(message = "Version negotiation failed") {
                    super(message), this.message = message, this.errorCode = 12, this.name = NegotiationFailedError.name;
                }
            }
            exports.NegotiationFailedError = NegotiationFailedError;
        },
        74374: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Response = void 0;
            exports.Response = class {
                constructor(request, result, error = void 0) {
                    this.result = result, this.error = error, this.requestId = request.requestId, this.name = request.name;
                }
            };
        },
        99669: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.ExceptionError = void 0;
            exports.ExceptionError = class {
                constructor(name, errorCode, message, stack) {
                    this.name = name, this.errorCode = errorCode, this.message = message, this.stack = stack;
                }
            };
        },
        92480: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.UnableToInjectScriptsError = void 0;
            class UnableToInjectScriptsError extends Error {
                constructor(message = "Unable to inject scripts") {
                    super(message), this.message = message, this.errorCode = 10, this.name = UnableToInjectScriptsError.name;
                }
            }
            exports.UnableToInjectScriptsError = UnableToInjectScriptsError;
        },
        75664: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.BackgroundV1 = void 0;
            __webpack_require__(17967);
            const response_1 = __webpack_require__(74374), responseError_1 = __webpack_require__(99669), logger_1 = __webpack_require__(88901), window_removed_notification_1 = __webpack_require__(72012), window_focused_changed_notification_1 = __webpack_require__(26702), window_created_notification_1 = __webpack_require__(17408), unableToInjectScriptsError_1 = __webpack_require__(92480);
            class BackgroundV1 {
                constructor(communicatorToNative, contentScriptVersionToLoad, apiScriptVersionToLoad) {
                    this.communicatorToNative = communicatorToNative, this.contentScriptVersionToLoad = contentScriptVersionToLoad, 
                    this.apiScriptVersionToLoad = apiScriptVersionToLoad, this.portsToTabs = {}, this.registerChromeEvents(), 
                    this.registerHostEvents(), this.addDefaultHandler(), logger_1.Logger.log("Background script V1 loaded");
                }
                static canScriptsBeInjected(tab) {
                    const url = tab.url;
                    return void 0 !== url && !(url.startsWith("chrome://") || url.startsWith("edge://") || url.startsWith("about:"));
                }
                static onGetTab(request) {
                    return chrome.tabs.get(request.tabId);
                }
                static onGetAllWindows() {
                    return chrome.windows.getAll({
                        populate: !0,
                        windowTypes: [ "normal" ]
                    });
                }
                static onGetAllTabs(request) {
                    return chrome.tabs.query({
                        windowId: request.windowId
                    });
                }
                static onActivateTab(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.update(request.tabId, {
                            active: !0
                        }), !0;
                    }));
                }
                static onRefreshPage(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.reload(request.tabId, {
                            bypassCache: !0
                        }), !0;
                    }));
                }
                static onNavigateToUrl(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const url = request.url;
                        return yield chrome.tabs.update(request.tabId, {
                            url
                        }), !0;
                    }));
                }
                static onCreateNewTab(request) {
                    const url = request.url;
                    return chrome.tabs.create({
                        url
                    });
                }
                static onCloseTab(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.remove(request.tabId), !0;
                    }));
                }
                static onClearCookies(_) {
                    return new Promise((p => {
                        chrome.browsingData.removeCookies({}, (() => p(!0)));
                    }));
                }
                static onClearCache(_) {
                    return new Promise((p => {
                        chrome.browsingData.removeCache({}, (() => p(!0)));
                    }));
                }
                static onSetZoom(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.setZoom(request.tabId, request.zoom), !0;
                    }));
                }
                static onGetZoom(request) {
                    return chrome.tabs.getZoom(request.tabId);
                }
                static onIsIeMode(request) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        try {
                            return yield chrome.scripting.executeScript({
                                target: {
                                    tabId: request.tabId
                                },
                                func: () => !0
                            }), !1;
                        } catch (e) {
                            return !0 === (null === (_a = e.message) || void 0 === _a ? void 0 : _a.startsWith("Frame with ID"));
                        }
                    }));
                }
                static onRunJavaScript(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (!(yield BackgroundV1.attachDebuggerIfNeeded(request.tabId))) throw new Error("Can't attach debugger");
                        return new Promise((resolve => {
                            chrome.debugger.sendCommand({
                                tabId: request.tabId
                            }, "Runtime.evaluate", {
                                expression: request.code
                            }, (result => {
                                chrome.debugger.detach({
                                    tabId: request.tabId
                                }, (() => {
                                    var _a;
                                    resolve((null !== (_a = result.result.value) && void 0 !== _a ? _a : result.result) + "");
                                }));
                            }));
                        }));
                    }));
                }
                static attachDebuggerIfNeeded(tabId) {
                    return new Promise((resolve => chrome.debugger.getTargets((targets => {
                        for (let i = 0; i < targets.length; i++) if (targets[i].tabId === tabId) return targets[i].attached ? void resolve(!1) : void chrome.debugger.attach({
                            tabId
                        }, "1.2", (() => {
                            resolve(!0);
                        }));
                        resolve(!1);
                    }))));
                }
                dispose() {
                    this.unRegisterChromeEvents(), this.unRegisterHostEvents(), this.lastForwardPort = void 0, 
                    this.lastMessage = void 0, this.portsToTabs = {}, logger_1.Logger.log("Background script V1 unloaded");
                }
                setupTabConnection(port, tab) {
                    var _a;
                    const customPort = port, tabId = null !== (_a = tab.id) && void 0 !== _a ? _a : 0;
                    return customPort.windowId = tab.windowId, customPort.tabId = tabId, this.portsToTabs[tabId] = customPort, 
                    port.onDisconnect.addListener((disconnectedPort => {
                        logger_1.Logger.groupLogging((() => {
                            var _a;
                            this.lastForwardPort && this.lastMessage && ("RunScript" === (null === (_a = this.lastMessage) || void 0 === _a ? void 0 : _a.name) ? this.communicatorToNative.post(new response_1.Response(this.lastMessage, "")) : this.communicatorToNative.post(new response_1.Response(this.lastMessage, void 0, new responseError_1.ExceptionError(`Tab with id ${this.lastForwardPort.tabId} is no longer available.`, 1))), 
                            this.lastForwardPort = void 0, this.lastMessage = void 0), this.portsToTabs[tabId] === disconnectedPort ? (logger_1.Logger.log("Removing disconnected tab port from registry"), 
                            this.portsToTabs[tabId] = null, delete this.portsToTabs[tabId]) : logger_1.Logger.warn("Disconnected tab port not found in the registry");
                        }), "Tab port disconnected. Id", tab.id);
                    })), customPort;
                }
                sendMessage(newPort, message) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return this.lastForwardPort = newPort, this.lastMessage = message, logger_1.Logger.log("Sending message to tab:", newPort.tabId, message), 
                        new Promise((resolve => {
                            const onMessage = m => {
                                logger_1.Logger.log("Received Message: ", m), m.requestId === message.requestId && (newPort.onMessage.removeListener(onMessage), 
                                resolve(m));
                            };
                            newPort.onMessage.addListener(onMessage), newPort.postMessage(message);
                        }));
                    }));
                }
                onMessageReceivedFromNativeHostForContent(message) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const contentScriptRequest = message;
                        return logger_1.Logger.groupLoggingAsync((() => __awaiter(this, void 0, void 0, (function*() {
                            if (void 0 !== contentScriptRequest && void 0 !== contentScriptRequest.tabId) {
                                let port = this.portsToTabs[contentScriptRequest.tabId];
                                if (null == port) {
                                    logger_1.Logger.log("Connecting to tab", contentScriptRequest.tabId);
                                    const tab = yield chrome.tabs.get(contentScriptRequest.tabId);
                                    if (!BackgroundV1.canScriptsBeInjected(tab)) return;
                                    yield this.injectScripts(contentScriptRequest.tabId), port = this.setupTabConnection(chrome.tabs.connect(contentScriptRequest.tabId, void 0), tab);
                                }
                                return this.sendMessage(port, message);
                            }
                            throw logger_1.Logger.error("Message is not ContentScriptRequest", message), new Error("Request is not ContentScriptRequest");
                        }))), "Default handling for message", message);
                    }));
                }
                injectScripts(tabId) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const contentScriptPath = `scripts/content.v${this.contentScriptVersionToLoad}.js`, apiScriptPath = `scripts/api.v${this.apiScriptVersionToLoad}.js`;
                        logger_1.Logger.log("Injecting scripts to tab: ", tabId);
                        try {
                            0, yield chrome.scripting.executeScript({
                                target: {
                                    tabId
                                },
                                files: [ contentScriptPath, apiScriptPath ]
                            });
                        } catch (e) {
                            throw new unableToInjectScriptsError_1.UnableToInjectScriptsError(e.message);
                        }
                    }));
                }
                addDefaultHandler() {
                    this.communicatorToNative.addDefaultHandler((message => this.onMessageReceivedFromNativeHostForContent(message)));
                }
                registerHostEvents() {
                    this.communicatorToNative.on("GetTabRequest", (m => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV1.onGetTab(m.parameters);
                    })))), this.communicatorToNative.on("GetAllWindowsRequest", (() => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV1.onGetAllWindows();
                    })))), this.communicatorToNative.on("GetAllTabsRequest", (m => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV1.onGetAllTabs(m.parameters);
                    })))), this.communicatorToNative.on("ActivateTabRequest", (m => BackgroundV1.onActivateTab(m.parameters))), 
                    this.communicatorToNative.on("RefreshPageRequest", (m => BackgroundV1.onRefreshPage(m.parameters))), 
                    this.communicatorToNative.on("NavigateToUrlRequest", (m => BackgroundV1.onNavigateToUrl(m.parameters))), 
                    this.communicatorToNative.on("CreateNewTabRequest", (m => BackgroundV1.onCreateNewTab(m.parameters))), 
                    this.communicatorToNative.on("CloseTabRequest", (m => BackgroundV1.onCloseTab(m.parameters))), 
                    this.communicatorToNative.on("ClearCookiesRequest", (m => BackgroundV1.onClearCookies(m))), 
                    this.communicatorToNative.on("ClearCacheRequest", (m => BackgroundV1.onClearCache(m))), 
                    this.communicatorToNative.on("SetZoomRequest", (m => BackgroundV1.onSetZoom(m.parameters))), 
                    this.communicatorToNative.on("GetZoomRequest", (m => BackgroundV1.onGetZoom(m.parameters))), 
                    this.communicatorToNative.on("IsIEModeTabRequest", (m => BackgroundV1.onIsIeMode(m.parameters))), 
                    this.communicatorToNative.on("RunJavaScriptRequest", (m => BackgroundV1.onRunJavaScript(m.parameters)));
                }
                unRegisterHostEvents() {
                    this.communicatorToNative.removeHandler("GetTabRequest"), this.communicatorToNative.removeHandler("GetAllWindowsRequest"), 
                    this.communicatorToNative.removeHandler("GetAllTabsRequest"), this.communicatorToNative.removeHandler("ActivateTabRequest"), 
                    this.communicatorToNative.removeHandler("RefreshPageRequest"), this.communicatorToNative.removeHandler("NavigateToUrlRequest"), 
                    this.communicatorToNative.removeHandler("CreateNewTabRequest"), this.communicatorToNative.removeHandler("CloseTabRequest"), 
                    this.communicatorToNative.removeHandler("ClearCookiesRequest"), this.communicatorToNative.removeHandler("ClearCacheRequest"), 
                    this.communicatorToNative.removeHandler("SetZoomRequest"), this.communicatorToNative.removeHandler("GetZoomRequest"), 
                    this.communicatorToNative.removeHandler("IsIEModeTabRequest"), this.communicatorToNative.removeHandler("RunJavaScriptRequest");
                }
                onWindowCreated(window) {
                    var _a;
                    console.log(`Window created. WindowId: ${window.id}`), this.communicatorToNative.post(new window_created_notification_1.WindowCreatedNotification(null !== (_a = window.id) && void 0 !== _a ? _a : 0));
                }
                onWindowFocusChanged(windowId) {
                    windowId !== chrome.windows.WINDOW_ID_NONE && (console.log(`Window focused. WindowId: ${windowId}`), 
                    this.communicatorToNative.post(new window_focused_changed_notification_1.WindowFocusedChangedNotification(windowId)));
                }
                onWindowRemoved(windowId) {
                    console.log(`Window removed. WindowId: ${windowId}`), this.communicatorToNative.post(new window_removed_notification_1.WindowRemovedNotification(windowId));
                }
                unRegisterChromeEvents() {
                    chrome.windows.onCreated.removeListener(this.onWindowCreatedCallback), chrome.windows.onFocusChanged.removeListener(this.onWindowFocusChangedCallback), 
                    chrome.windows.onRemoved.removeListener(this.onWindowRemovedCallback);
                }
                registerChromeEvents() {
                    const script = this;
                    this.onWindowCreatedCallback = window => script.onWindowCreated(window), this.onWindowFocusChangedCallback = windowId => script.onWindowFocusChanged(windowId), 
                    this.onWindowRemovedCallback = windowId => script.onWindowRemoved(windowId), chrome.windows.onCreated.addListener(this.onWindowCreatedCallback), 
                    chrome.windows.onFocusChanged.addListener(this.onWindowFocusChangedCallback), chrome.windows.onRemoved.addListener(this.onWindowRemovedCallback);
                }
            }
            exports.BackgroundV1 = BackgroundV1;
        },
        62752: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Notification = void 0;
            exports.Notification = class {
                constructor(notify) {
                    this.notify = notify, this.name = "notify", this.requestId = "";
                }
            };
        },
        17408: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowCreatedNotification = void 0;
            const notification_1 = __webpack_require__(62752);
            class WindowCreatedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_created"), this.windowId = windowId;
                }
            }
            exports.WindowCreatedNotification = WindowCreatedNotification;
        },
        26702: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowFocusedChangedNotification = void 0;
            const notification_1 = __webpack_require__(62752);
            class WindowFocusedChangedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_focused"), this.windowId = windowId;
                }
            }
            exports.WindowFocusedChangedNotification = WindowFocusedChangedNotification;
        },
        72012: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowRemovedNotification = void 0;
            const notification_1 = __webpack_require__(62752);
            class WindowRemovedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_removed"), this.windowId = windowId;
                }
            }
            exports.WindowRemovedNotification = WindowRemovedNotification;
        },
        22206: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.ExtractionResult = void 0;
            class ExtractionResult {
                constructor(status, data, error) {
                    this.status = status, this.data = data, this.error = error;
                }
                static pending() {
                    return new ExtractionResult("pending", null, null);
                }
                static complete(data) {
                    return new ExtractionResult("complete", data, null);
                }
                static error(error) {
                    return new ExtractionResult("error", null, error);
                }
            }
            exports.ExtractionResult = ExtractionResult;
        },
        21887: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.TabApi = void 0;
            const frame_1 = __webpack_require__(28230), response_1 = __webpack_require__(74374), logger_1 = __webpack_require__(88901), can_scripts_be_injected_1 = __webpack_require__(9805), extraction_result_1 = __webpack_require__(22206), unableToInjectScriptsError_1 = __webpack_require__(92480), execute_with_timeout_1 = __webpack_require__(87555);
            class TabApi {
                constructor(tab, contentScriptVersionToLoad, apiScriptVersionToLoad) {
                    var _a;
                    this.tab = tab, this.id = null !== (_a = this.tab.id) && void 0 !== _a ? _a : 0, 
                    this.contentScriptPath = `scripts/content.v${contentScriptVersionToLoad}.js`, this.apiScriptPath = `scripts/api.v${apiScriptVersionToLoad}.js`;
                }
                dispose() {
                    logger_1.Logger.log("Disposed tab", this.tab.id);
                }
                execute(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return logger_1.Logger.groupLoggingAsync((() => __awaiter(this, void 0, void 0, (function*() {
                            switch (request.name) {
                              case "GetAncestorListRequest":
                                return this.getAncestorList(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetElementFromPointRequest":
                                return this.getElementFromPoint(request);

                              case "GetElementRectangleRequest":
                                return this.getElementRectangle(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetElementRequest":
                              case "GetPreviousSiblingRequest":
                              case "GetNextSiblingRequest":
                                return this.getElement(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetChildrenRequest":
                                return this.getChildren(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetFocusedElementRequest":
                                return this.getFocusedElement(request);

                              case "GetIndexOfElementRequest":
                                return this.getIndexOfElement(request);

                              case "GetParentRequest":
                                return this.getParent(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "InitiateDataExtractionRequest":
                                return this.initiateDataExtraction(request);

                              case "GetExtractionResultRequest":
                                return this.getExtractionResult(request);

                              case "SmartSearchTextRequest":
                                return this.anyFrameReturnsTrue(request);

                              case "PreparePageForExtractionRequest":
                              case "ResetUniverseRequest":
                              case "RevertPermanentHighlightingOfCurrentElementsRequest":
                                return this.allFramesReturnTrue(request);

                              case "TestSelectorRequest":
                                return this.testSelector(request);

                              default:
                                return this.defaultHandler(request);
                            }
                        }))), "Handling for request: ", request);
                    }));
                }
                defaultHandler(request) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (null !== (_a = request.frameId) && void 0 !== _a || (request.frameId = frame_1.Frame.MainFrame), 
                        TabApi.isValidCssSelectorContentScriptRequest(request)) {
                            const cssSelectorRequest = request, cssSelector = cssSelectorRequest.parameters.cssSelectorPerFrame.pop(), frame = yield this.findSubFrameBySelectors(request.requestId, cssSelectorRequest.parameters.cssSelectorPerFrame);
                            if (!frame) throw new Error("Frame is not available.");
                            request.frameId = frame.id, request.parameters.cssSelector = cssSelector, request.parameters.cssSelectorPerFrame = void 0;
                        }
                        return this.sendMessage(request);
                    }));
                }
                testSelector(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let frame = yield this.getFrame(frame_1.Frame.MainFrame), nodesFound = 0, result = null;
                        const selectorsPerFrame = null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : [];
                        for (let i = 0; i < selectorsPerFrame.length; i++) {
                            request.parameters.cssSelector = selectorsPerFrame[i], request.parameters.selectorElements = request.parameters.selectorElementsPerFrame[i], 
                            request.parameters.cssSelectorPerFrame = void 0, request.frameId = null == frame ? void 0 : frame.id;
                            const response = yield this.defaultHandler(request);
                            if (null == response || response.error) return response;
                            if (0 === response.result.elementsMatched) return response.result.elementNodesMatched += nodesFound, 
                            response;
                            result = response, nodesFound += response.result.elementNodesMatched, frame = yield this.findSubFrameBySelector(request.requestId, selectorsPerFrame[i], frame);
                        }
                        return null !== result && (result.result.elementNodesMatched = nodesFound), result;
                    }));
                }
                allFramesReturnTrue(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        for (const frame of yield this.getAllFrames()) {
                            request.frameId = null == frame ? void 0 : frame.id;
                            const response = yield this.defaultHandler(request);
                            if (null == response || void 0 !== response.error || !response.result) return new response_1.Response(request, !1, null == response ? void 0 : response.error);
                        }
                        return new response_1.Response(request, !0);
                    }));
                }
                anyFrameReturnsTrue(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        for (const frame of yield this.getAllFrames()) {
                            request.frameId = null == frame ? void 0 : frame.id;
                            const response = yield this.defaultHandler(request);
                            if (null == response || void 0 !== response.error) return new response_1.Response(request, !1, null == response ? void 0 : response.error);
                            if (response.result) return new response_1.Response(request, !0);
                        }
                        return new response_1.Response(request, !1);
                    }));
                }
                extractHandpickedData(request) {
                    var _a, _b, _c;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let result = [];
                        const selectors = Array.from(null !== (_c = null === (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.parameters) || void 0 === _b ? void 0 : _b.selectors) && void 0 !== _c ? _c : []);
                        for (const selector of selectors) {
                            const response = yield this.defaultHandler({
                                name: request.name,
                                requestId: crypto.randomUUID(),
                                tabId: request.tabId,
                                parameters: {
                                    cssSelectorPerFrame: selector.frameSelectors,
                                    isDesignTime: request.parameters.isDesignTime,
                                    parameters: {
                                        selectors: [ {
                                            selector: selector.frameSelectors[selector.frameSelectors.length - 1],
                                            attribute: selector.attribute
                                        } ]
                                    },
                                    type: request.parameters.type
                                }
                            });
                            result = result.concat(response.result);
                        }
                        return result;
                    }));
                }
                getAncestorList(request) {
                    var _a, _b, _c, _d, _e;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let frame = null, resultCollection = [], selector = null;
                        const frameSelectors = null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : [];
                        for (const frameSelector of frameSelectors) {
                            request.parameters = {
                                cssSelector: frameSelector,
                                cssSelectorPerFrame: void 0
                            };
                            const response = yield this.defaultHandler(request);
                            if (null == response || response.error || void 0 === response.result || null === response.result || 0 === response.result.length) break;
                            null !== selector && response.result.forEach((element => element.cssSelectorString = `${selector} > ${element.cssSelectorString}`));
                            const lastElement = response.result[response.result.length - 1];
                            if (selector = lastElement.cssSelectorString, resultCollection = resultCollection.concat(response.result), 
                            "iframe" !== (null === (_c = lastElement.tag) || void 0 === _c ? void 0 : _c.toLowerCase()) && "frame" !== (null === (_d = lastElement.tag) || void 0 === _d ? void 0 : _d.toLowerCase())) break;
                            frame = yield this.findSubFrameBySelector(request.requestId, frameSelector, frame), 
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return "html" === (null === (_e = resultCollection[0].tag) || void 0 === _e ? void 0 : _e.toLowerCase()) && resultCollection.shift(), 
                        new response_1.Response(request, resultCollection);
                    }));
                }
                getChildren(request) {
                    var _a, _b, _c, _d, _e, _f;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const frameSelectors = Array.from(null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : []), element = yield this.defaultHandler({
                            name: "GetElementRequest",
                            requestId: request.requestId,
                            parameters: {
                                cssSelector: null === (_c = request.parameters) || void 0 === _c ? void 0 : _c.cssSelector,
                                cssSelectorPerFrame: [ ...frameSelectors ]
                            },
                            tabId: this.id
                        }), elementTag = null === (_e = null === (_d = null == element ? void 0 : element.result) || void 0 === _d ? void 0 : _d.tag) || void 0 === _e ? void 0 : _e.toLowerCase();
                        if ("iframe" === elementTag || "frame" === elementTag) {
                            const frame = yield this.findSubFrameBySelectors(request.requestId, null === (_f = request.parameters) || void 0 === _f ? void 0 : _f.cssSelectorPerFrame), htmlElement = yield this.defaultHandler({
                                name: "GetElementRequest",
                                requestId: request.requestId,
                                frameId: frame.id,
                                parameters: {
                                    cssSelector: "html"
                                },
                                tabId: this.id
                            });
                            return null == htmlElement || htmlElement.error ? new response_1.Response(request, null, null == htmlElement ? void 0 : htmlElement.error) : (htmlElement.result.cssSelectorString = `${frameSelectors.join(" > ")} > ${htmlElement.result.cssSelectorString}`, 
                            new response_1.Response(request, [ htmlElement.result ]));
                        }
                        const response = yield this.defaultHandler(request);
                        if (null == response) return response;
                        if (void 0 !== response.result && null !== response.result) {
                            frameSelectors.pop();
                            const children = response.result.map((c => (c.cssSelectorString = [ ...frameSelectors, c.cssSelectorString ].join(" > "), 
                            c)));
                            return new response_1.Response(request, children);
                        }
                        return response;
                    }));
                }
                getElementFromPoint(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let x = 0, y = 0, selector = null, frame = null, result = null;
                        for (;;) {
                            const message = yield this.defaultHandler(request), response = message;
                            if (null == response || response.error) return message;
                            result = response.result;
                            const offsetX = result.rectangleProperties.elementOffsetLeft - result.rectangleProperties.viewPortScrollLeft, offsetY = result.rectangleProperties.elementOffsetTop - result.rectangleProperties.viewPortScrollTop;
                            if (x += offsetX, y += offsetY, selector = null === selector ? result.cssSelectorString : `${selector} > ${result.cssSelectorString}`, 
                            "iframe" !== (null === (_a = result.tag) || void 0 === _a ? void 0 : _a.toLowerCase()) && "frame" !== (null === (_b = result.tag) || void 0 === _b ? void 0 : _b.toLowerCase())) break;
                            if (request.parameters.x -= offsetX + result.rectangleProperties.paddingLeft, request.parameters.y -= offsetY + result.rectangleProperties.paddingTop, 
                            frame = yield this.findSubFrameBySelector(request.requestId, result.cssSelectorString, frame), 
                            null === frame) break;
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return result.rectangleProperties.elementOffsetLeft = x, result.rectangleProperties.elementOffsetTop = y, 
                        result.cssSelectorString = selector, new response_1.Response(request, result);
                    }));
                }
                getElement(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const frameSelectors = Array.from(null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : []);
                        frameSelectors.pop();
                        const response = yield this.defaultHandler(request);
                        return null == response ? response : void 0 !== response.result && null !== response.result ? (frameSelectors.push(response.result.cssSelectorString), 
                        response.result.cssSelectorString = frameSelectors.join(" > "), response) : response;
                    }));
                }
                getElementRectangle(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let x = 0, y = 0, frame = null, result = null;
                        const frameSelectors = null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : [];
                        for (const frameSelector of frameSelectors) {
                            request.parameters = {
                                cssSelector: frameSelector,
                                cssSelectorPerFrame: void 0
                            };
                            const response = yield this.defaultHandler(request);
                            if (null == response || response.error) return new response_1.Response(request, null, null == response ? void 0 : response.error);
                            result = response.result, x += result.elementOffsetLeft, y += result.elementOffsetTop, 
                            frameSelectors.indexOf(frameSelector) !== frameSelectors.length - 1 && (x -= result.viewPortScrollLeft - result.paddingLeft, 
                            y -= result.viewPortScrollTop - result.paddingTop), frame = yield this.findSubFrameBySelector(request.requestId, frameSelector, frame), 
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return null !== result && (result.elementOffsetLeft = x, result.elementOffsetTop = y), 
                        new response_1.Response(request, result);
                    }));
                }
                getExtractionResult(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return new Promise(((resolve, _rejected) => {
                            resolve(new response_1.Response(request, this.extractionResult));
                        }));
                    }));
                }
                getFocusedElement(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let x = 0, y = 0, selector = null, frame = null, result = null;
                        for (;;) {
                            const message = yield this.defaultHandler(request), response = message;
                            if (null == response || response.error) return message;
                            if (result = response.result, x += result.rectangleProperties.elementOffsetLeft - result.rectangleProperties.viewPortScrollLeft, 
                            y += result.rectangleProperties.elementOffsetTop - result.rectangleProperties.viewPortScrollTop, 
                            selector = null === selector ? result.cssSelectorString : `${selector} > ${result.cssSelectorString}`, 
                            "iframe" !== (null === (_a = result.tag) || void 0 === _a ? void 0 : _a.toLowerCase()) && "frame" !== (null === (_b = result.tag) || void 0 === _b ? void 0 : _b.toLowerCase())) break;
                            if (frame = yield this.findSubFrameBySelector(request.requestId, result.cssSelectorString, frame), 
                            null === frame) break;
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return result.rectangleProperties.elementOffsetLeft = x, result.rectangleProperties.elementOffsetTop = y, 
                        result.cssSelectorString = selector, new response_1.Response(request, result);
                    }));
                }
                getIndexOfElement(request) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const parameters = request.parameters;
                        return parameters.specificElementCssSelector = null === (_a = parameters.specificElementCssSelectorPerFrame) || void 0 === _a ? void 0 : _a.pop(), 
                        parameters.specificElementCssSelectorPerFrame = void 0, this.defaultHandler(request);
                    }));
                }
                getParent(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const frameSelectors = Array.from(null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : []);
                        frameSelectors.pop();
                        const response = yield this.defaultHandler(request);
                        return null == response ? response : void 0 !== response.result && null !== response.result ? (frameSelectors.push(response.result.cssSelectorString), 
                        response.result.cssSelectorString = frameSelectors.join(" > "), response) : frameSelectors.length > 0 ? (request.parameters = {
                            cssSelector: frameSelectors[frameSelectors.length - 1],
                            cssSelectorPerFrame: frameSelectors
                        }, request.name = "GetElementRequest", this.defaultHandler(request)) : response;
                    }));
                }
                initiateDataExtraction(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return this.extractionResult = extraction_result_1.ExtractionResult.pending(), setTimeout((() => __awaiter(this, void 0, void 0, (function*() {
                            var _a;
                            try {
                                if (TabApi.isValidExtractHandpickedValuesRequest(request)) return void (this.extractionResult = extraction_result_1.ExtractionResult.complete(yield this.extractHandpickedData(request)));
                                if (TabApi.isValidCssSelectorContentScriptRequest(request)) return void (this.extractionResult = extraction_result_1.ExtractionResult.complete(null === (_a = yield this.defaultHandler(request)) || void 0 === _a ? void 0 : _a.result));
                                this.extractionResult = extraction_result_1.ExtractionResult.error("InitiateDataExtractionRequest is not in valid format.");
                            } catch (e) {
                                this.extractionResult = extraction_result_1.ExtractionResult.error(e.toString());
                            }
                        }))), 0), new Promise(((resolve, _rejected) => {
                            resolve(new response_1.Response(request, !0));
                        }));
                    }));
                }
                getPort(frameId) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const $frame = yield this.getFrame(frameId);
                        if (!$frame || $frame.id !== frameId || !(0, can_scripts_be_injected_1.canScriptsBeInjected)($frame.url)) return null;
                        if (!($frame.isMain() ? yield this.injectScriptsToMainFrame() : yield this.injectScriptsToSubFrame($frame.id))) return null;
                        const port = chrome.tabs.connect(this.id, {
                            frameId
                        });
                        return port || (logger_1.Logger.warn(`Port to frame '${frameId}' at tab '${this.id}' could not be created.`), 
                        null);
                    }));
                }
                injectScriptsToMainFrame() {
                    return __awaiter(this, void 0, void 0, (function*() {
                        try {
                            return (yield chrome.scripting.executeScript({
                                target: {
                                    tabId: this.id,
                                    frameIds: [ frame_1.Frame.MainFrame ]
                                },
                                func: () => globalThis._padScriptLoaded_E2C4773F
                            }))[0].result || (logger_1.Logger.log("Injecting scripts to main frame at tab: ", this.id), 
                            yield chrome.scripting.executeScript({
                                target: {
                                    tabId: this.id,
                                    frameIds: [ frame_1.Frame.MainFrame ]
                                },
                                files: [ this.contentScriptPath, this.apiScriptPath ]
                            }), logger_1.Logger.log("Injected scripts to main frame at tab: ", this.id)), !0;
                        } catch (e) {
                            throw logger_1.Logger.error("Unable to inject scripts to main frame at tab: ", this.id, " with exception", e.message), 
                            new unableToInjectScriptsError_1.UnableToInjectScriptsError(e.message);
                        }
                    }));
                }
                injectScriptsToSubFrame(frameId) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const tab = this;
                        return (0, execute_with_timeout_1.executeWithTimeout)(TabApi.injectionTimeOut, function() {
                            return __awaiter(this, void 0, void 0, (function*() {
                                try {
                                    return (yield chrome.scripting.executeScript({
                                        target: {
                                            tabId: tab.id,
                                            frameIds: [ frameId ]
                                        },
                                        func: () => globalThis._padScriptLoaded_E2C4773F
                                    }))[0].result || (logger_1.Logger.log("Injecting scripts to frame: ", frameId, " at tab: ", tab.id), 
                                    yield chrome.scripting.executeScript({
                                        target: {
                                            tabId: tab.id,
                                            frameIds: [ frameId ]
                                        },
                                        files: [ tab.contentScriptPath, tab.apiScriptPath ]
                                    }), logger_1.Logger.log("Injected scripts to frame: ", frameId, " at tab: ", tab.id)), 
                                    !0;
                                } catch (e) {
                                    return logger_1.Logger.error("Unable to inject scripts to frame: ", frameId, " at tab: ", tab.id, " with exception", e.message), 
                                    !1;
                                }
                            }));
                        }(), !1);
                    }));
                }
                sendMessage(message) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const messagePort = yield this.getPort(message.frameId);
                        return new Promise(((resolve, reject) => {
                            const onMessage = m => {
                                logger_1.Logger.log("Received Message: ", m), m.requestId === message.requestId && (removeHandlers(), 
                                resolve(m), messagePort.disconnect());
                            }, onDisconnect = _ => {
                                logger_1.Logger.error("Port disconnected: ", message), removeHandlers(), reject("Port disconnected");
                            }, removeHandlers = () => {
                                messagePort.onMessage.removeListener(onMessage), messagePort.onDisconnect.removeListener(onDisconnect);
                            };
                            messagePort.onMessage.addListener(onMessage), messagePort.onDisconnect.addListener(onDisconnect);
                            try {
                                logger_1.Logger.log("Sending message to tab:", this.id, "and frame:", message.frameId, message), 
                                messagePort.postMessage(message);
                            } catch (e) {
                                logger_1.Logger.error("Failed to post message: ", message, e), messagePort.disconnect(), 
                                removeHandlers(), reject(e);
                            }
                        }));
                    }));
                }
                getAllFrames() {
                    return new Promise(((resolve, rejected) => {
                        chrome.webNavigation.getAllFrames({
                            tabId: this.id
                        }, (frames => {
                            null == frames || frames.length <= 0 ? rejected("No frames were returned.") : resolve(frames.map((frame => new frame_1.Frame({
                                id: frame.frameId,
                                tabId: this.id,
                                parentFrameId: frame.parentFrameId,
                                url: frame.url
                            }))));
                        }));
                    }));
                }
                getFrame(frameId) {
                    return new Promise(((resolve, rejected) => {
                        chrome.webNavigation.getFrame({
                            tabId: this.id,
                            frameId
                        }, (frame => {
                            frame ? resolve(new frame_1.Frame({
                                id: frameId,
                                tabId: this.id,
                                parentFrameId: frame.parentFrameId,
                                url: frame.url
                            })) : rejected("No frame was returned.");
                        }));
                    }));
                }
                findSubFrameBySelector(requestId, selector, currentFrame) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (null != currentFrame || (currentFrame = yield this.getFrame(frame_1.Frame.MainFrame)), 
                        !currentFrame) return null;
                        if (selector.toLowerCase().indexOf("frame") <= -1) return currentFrame;
                        const response = yield this.defaultHandler({
                            name: "GetIndexOfFrameRequest",
                            requestId,
                            frameId: currentFrame.id,
                            parameters: {
                                cssSelector: selector
                            },
                            tabId: this.id
                        });
                        if ((null == response ? void 0 : response.requestId) !== requestId) return null;
                        if (void 0 === (null == response ? void 0 : response.result) || null === (null == response ? void 0 : response.result) || response.error) return (null === (_a = null == response ? void 0 : response.error) || void 0 === _a ? void 0 : _a.errorCode) === TabApi.noframeErrorCode ? currentFrame : null;
                        for (const frame of yield this.getAllFrames()) if (frame.parentFrameId === currentFrame.id && (yield frame.isAt(response.result))) return frame;
                        return null;
                    }));
                }
                findSubFrameBySelectors(requestId, selectors) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        let currentFrame = yield this.getFrame(frame_1.Frame.MainFrame);
                        if (!currentFrame) return null;
                        for (const selector of selectors) if (currentFrame = yield this.findSubFrameBySelector(requestId, selector, currentFrame), 
                        null == currentFrame) break;
                        return currentFrame;
                    }));
                }
                static validateCssSelectorContentScriptRequest(request) {
                    if (!TabApi.isValidCssSelectorContentScriptRequest(request)) throw logger_1.Logger.error("Message is not CssSelectorContentScriptRequest", request), 
                    new Error("Request is not CssSelectorContentScriptRequest");
                    return request;
                }
                static isValidCssSelectorContentScriptRequest(request) {
                    var _a, _b;
                    const cssSelectorContentScriptRequest = request;
                    return void 0 !== (null === (_a = cssSelectorContentScriptRequest.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && null !== (null === (_b = cssSelectorContentScriptRequest.parameters) || void 0 === _b ? void 0 : _b.cssSelectorPerFrame) && cssSelectorContentScriptRequest.parameters.cssSelectorPerFrame.length > 0;
                }
                static isValidExtractHandpickedValuesRequest(request) {
                    var _a, _b, _c, _d, _e;
                    const extractDataContentScriptRequest = request;
                    return void 0 !== (null === (_b = null === (_a = null == extractDataContentScriptRequest ? void 0 : extractDataContentScriptRequest.parameters) || void 0 === _a ? void 0 : _a.parameters) || void 0 === _b ? void 0 : _b.selectors) && null !== (null === (_d = null === (_c = null == extractDataContentScriptRequest ? void 0 : extractDataContentScriptRequest.parameters) || void 0 === _c ? void 0 : _c.parameters) || void 0 === _d ? void 0 : _d.selectors) && (null === (_e = null == extractDataContentScriptRequest ? void 0 : extractDataContentScriptRequest.parameters) || void 0 === _e ? void 0 : _e.parameters.selectors.length) > 0;
                }
            }
            exports.TabApi = TabApi, TabApi.injectionTimeOut = 500, TabApi.noframeErrorCode = 11;
        },
        34968: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.BackgroundV2 = void 0;
            __webpack_require__(17967);
            const logger_1 = __webpack_require__(88901), window_removed_notification_1 = __webpack_require__(25746), window_focused_changed_notification_1 = __webpack_require__(93212), window_created_notification_1 = __webpack_require__(87466), tab_api_1 = __webpack_require__(21887), can_scripts_be_injected_1 = __webpack_require__(9805), execute_with_timeout_1 = __webpack_require__(87555);
            class BackgroundV2 {
                constructor(communicatorToNative, contentScriptVersionToLoad, apiScriptVersionToLoad) {
                    this.communicatorToNative = communicatorToNative, this.contentScriptVersionToLoad = contentScriptVersionToLoad, 
                    this.apiScriptVersionToLoad = apiScriptVersionToLoad, this.tabs = {}, this.registerChromeEvents(), 
                    this.registerHostEvents(), logger_1.Logger.log("Background script V2 loaded");
                }
                static onGetTab(request) {
                    return chrome.tabs.get(request.tabId);
                }
                static onGetAllWindows() {
                    return chrome.windows.getAll({
                        populate: !0,
                        windowTypes: [ "normal" ]
                    });
                }
                static onGetAllTabs(request) {
                    return chrome.tabs.query({
                        windowId: request.windowId
                    });
                }
                static onActivateTab(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.update(request.tabId, {
                            active: !0
                        }), !0;
                    }));
                }
                static onRefreshPage(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.reload(request.tabId, {
                            bypassCache: !0
                        }), !0;
                    }));
                }
                static onNavigateToUrl(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const url = request.url;
                        return yield chrome.tabs.update(request.tabId, {
                            url
                        }), !0;
                    }));
                }
                static onCreateNewTab(request) {
                    const url = request.url;
                    return chrome.tabs.create({
                        url
                    });
                }
                static onCloseTab(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.remove(request.tabId), !0;
                    }));
                }
                static onClearCookies(_) {
                    return new Promise((p => chrome.browsingData.removeCookies({}, (() => p(!0)))));
                }
                static onClearCache(_) {
                    return new Promise((p => chrome.browsingData.removeCache({}, (() => p(!0)))));
                }
                static onSetZoom(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.setZoom(request.tabId, request.zoom), !0;
                    }));
                }
                static onGetZoom(request) {
                    return chrome.tabs.getZoom(request.tabId);
                }
                static onIsIeMode(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return (0, execute_with_timeout_1.executeWithTimeout)(100, function() {
                            var _a;
                            return __awaiter(this, void 0, void 0, (function*() {
                                try {
                                    return yield chrome.scripting.executeScript({
                                        target: {
                                            tabId: request.tabId
                                        },
                                        func: () => !0
                                    }), !1;
                                } catch (e) {
                                    return !0 === (null === (_a = e.message) || void 0 === _a ? void 0 : _a.startsWith("Frame with ID"));
                                }
                            }));
                        }(), !1);
                    }));
                }
                static onRunJavaScript(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (!(yield BackgroundV2.attachDebuggerIfNeeded(request.tabId))) throw new Error("Can't attach debugger");
                        return new Promise((resolve => {
                            chrome.debugger.sendCommand({
                                tabId: request.tabId
                            }, "Runtime.evaluate", {
                                expression: request.code
                            }, (result => {
                                chrome.debugger.detach({
                                    tabId: request.tabId
                                }, (() => {
                                    var _a;
                                    resolve(`${null !== (_a = result.result.value) && void 0 !== _a ? _a : result.result}`);
                                }));
                            }));
                        }));
                    }));
                }
                removeTab(tabId) {
                    this.tabs[tabId] && (logger_1.Logger.log("Tab removed: ", this.tabs[tabId]), this.tabs[tabId].dispose(), 
                    delete this.tabs[tabId]);
                }
                static attachDebuggerIfNeeded(tabId) {
                    return new Promise((resolve => chrome.debugger.getTargets((targets => {
                        for (let i = 0; i < targets.length; i++) if (targets[i].tabId === tabId) return targets[i].attached ? void resolve(!1) : void chrome.debugger.attach({
                            tabId
                        }, "1.2", (() => {
                            resolve(!0);
                        }));
                        resolve(!1);
                    }))));
                }
                dispose() {
                    this.unRegisterChromeEvents(), this.unRegisterHostEvents(), Object.keys(this.tabs).forEach((key => {
                        this.tabs[key].dispose(), delete this.tabs[key];
                    })), this.tabs = void 0, logger_1.Logger.log("Background script V2 unloaded");
                }
                defaultHandler(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const $tab = yield chrome.tabs.get(request.tabId);
                        if ($tab && (0, can_scripts_be_injected_1.canScriptsBeInjected)($tab.url)) return void 0 !== this.tabs[request.tabId] && null !== this.tabs[request.tabId] || (this.tabs[request.tabId] = new tab_api_1.TabApi($tab, this.contentScriptVersionToLoad, this.apiScriptVersionToLoad)), 
                        this.tabs[request.tabId].execute(request);
                    }));
                }
                registerHostEvents() {
                    this.communicatorToNative.on("GetTabRequest", (m => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV2.onGetTab(m.parameters);
                    })))), this.communicatorToNative.on("GetAllWindowsRequest", (() => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV2.onGetAllWindows();
                    })))), this.communicatorToNative.on("GetAllTabsRequest", (m => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV2.onGetAllTabs(m.parameters);
                    })))), this.communicatorToNative.on("ActivateTabRequest", (m => BackgroundV2.onActivateTab(m.parameters))), 
                    this.communicatorToNative.on("RefreshPageRequest", (m => BackgroundV2.onRefreshPage(m.parameters))), 
                    this.communicatorToNative.on("NavigateToUrlRequest", (m => BackgroundV2.onNavigateToUrl(m.parameters))), 
                    this.communicatorToNative.on("CreateNewTabRequest", (m => BackgroundV2.onCreateNewTab(m.parameters))), 
                    this.communicatorToNative.on("CloseTabRequest", (m => BackgroundV2.onCloseTab(m.parameters))), 
                    this.communicatorToNative.on("ClearCookiesRequest", (m => BackgroundV2.onClearCookies(m))), 
                    this.communicatorToNative.on("ClearCacheRequest", (m => BackgroundV2.onClearCache(m))), 
                    this.communicatorToNative.on("SetZoomRequest", (m => BackgroundV2.onSetZoom(m.parameters))), 
                    this.communicatorToNative.on("GetZoomRequest", (m => BackgroundV2.onGetZoom(m.parameters))), 
                    this.communicatorToNative.on("IsIEModeTabRequest", (m => BackgroundV2.onIsIeMode(m.parameters))), 
                    this.communicatorToNative.on("RunJavaScriptRequest", (m => BackgroundV2.onRunJavaScript(m.parameters))), 
                    this.communicatorToNative.addDefaultHandler((m => this.defaultHandler(BackgroundV2.validateContentScriptRequest(m))));
                }
                unRegisterHostEvents() {
                    this.communicatorToNative.removeHandler("GetTabRequest"), this.communicatorToNative.removeHandler("GetAllWindowsRequest"), 
                    this.communicatorToNative.removeHandler("GetAllTabsRequest"), this.communicatorToNative.removeHandler("ActivateTabRequest"), 
                    this.communicatorToNative.removeHandler("RefreshPageRequest"), this.communicatorToNative.removeHandler("NavigateToUrlRequest"), 
                    this.communicatorToNative.removeHandler("CreateNewTabRequest"), this.communicatorToNative.removeHandler("CloseTabRequest"), 
                    this.communicatorToNative.removeHandler("ClearCookiesRequest"), this.communicatorToNative.removeHandler("ClearCacheRequest"), 
                    this.communicatorToNative.removeHandler("SetZoomRequest"), this.communicatorToNative.removeHandler("GetZoomRequest"), 
                    this.communicatorToNative.removeHandler("IsIEModeTabRequest"), this.communicatorToNative.removeHandler("RunJavaScriptRequest");
                }
                onWindowCreated(window) {
                    var _a;
                    console.log(`Window created. WindowId: ${window.id}`), this.communicatorToNative.post(new window_created_notification_1.WindowCreatedNotification(null !== (_a = window.id) && void 0 !== _a ? _a : 0));
                }
                onWindowFocusChanged(windowId) {
                    windowId !== chrome.windows.WINDOW_ID_NONE && (console.log(`Window focused. WindowId: ${windowId}`), 
                    this.communicatorToNative.post(new window_focused_changed_notification_1.WindowFocusedChangedNotification(windowId)));
                }
                onWindowRemoved(windowId) {
                    console.log(`Window removed. WindowId: ${windowId}`), this.communicatorToNative.post(new window_removed_notification_1.WindowRemovedNotification(windowId));
                }
                unRegisterChromeEvents() {
                    chrome.windows.onCreated.removeListener(this.onWindowCreatedCallback), chrome.windows.onFocusChanged.removeListener(this.onWindowFocusChangedCallback), 
                    chrome.windows.onRemoved.removeListener(this.onWindowRemovedCallback), chrome.tabs.onRemoved.removeListener(this.onTabRemovedCallback);
                }
                registerChromeEvents() {
                    const script = this;
                    this.onWindowCreatedCallback = window => script.onWindowCreated(window), this.onWindowFocusChangedCallback = windowId => script.onWindowFocusChanged(windowId), 
                    this.onWindowRemovedCallback = windowId => script.onWindowRemoved(windowId), this.onTabRemovedCallback = (tabId, _) => script.removeTab(tabId), 
                    chrome.windows.onCreated.addListener(this.onWindowCreatedCallback), chrome.windows.onFocusChanged.addListener(this.onWindowFocusChangedCallback), 
                    chrome.windows.onRemoved.addListener(this.onWindowRemovedCallback), chrome.tabs.onRemoved.addListener(this.onTabRemovedCallback);
                }
                static validateContentScriptRequest(request) {
                    const contentScript = request;
                    if (null == contentScript || void 0 === contentScript.tabId || null === contentScript.tabId) throw logger_1.Logger.error("Message is not ContentScriptRequest", request), 
                    new Error("Request is not ContentScriptRequest");
                    return contentScript;
                }
            }
            exports.BackgroundV2 = BackgroundV2;
        },
        65477: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Notification = void 0;
            exports.Notification = class {
                constructor(notify) {
                    this.notify = notify, this.name = "notify", this.requestId = "";
                }
            };
        },
        87466: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowCreatedNotification = void 0;
            const notification_1 = __webpack_require__(65477);
            class WindowCreatedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_created"), this.windowId = windowId;
                }
            }
            exports.WindowCreatedNotification = WindowCreatedNotification;
        },
        93212: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowFocusedChangedNotification = void 0;
            const notification_1 = __webpack_require__(65477);
            class WindowFocusedChangedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_focused"), this.windowId = windowId;
                }
            }
            exports.WindowFocusedChangedNotification = WindowFocusedChangedNotification;
        },
        25746: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowRemovedNotification = void 0;
            const notification_1 = __webpack_require__(65477);
            class WindowRemovedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_removed"), this.windowId = windowId;
                }
            }
            exports.WindowRemovedNotification = WindowRemovedNotification;
        },
        90367: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.ExtractionResult = void 0;
            class ExtractionResult {
                constructor(status, data, error) {
                    this.status = status, this.data = data, this.error = error;
                }
                static pending() {
                    return new ExtractionResult("pending", null, null);
                }
                static complete(data) {
                    return new ExtractionResult("complete", data, null);
                }
                static error(error) {
                    return new ExtractionResult("error", null, error);
                }
            }
            exports.ExtractionResult = ExtractionResult;
        },
        90738: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.TabApi = void 0;
            const frame_1 = __webpack_require__(28230), response_1 = __webpack_require__(74374), logger_1 = __webpack_require__(88901), can_scripts_be_injected_1 = __webpack_require__(9805), extraction_result_1 = __webpack_require__(90367), unableToInjectScriptsError_1 = __webpack_require__(92480), execute_with_timeout_1 = __webpack_require__(87555);
            class TabApi {
                constructor(tab, contentScriptVersionToLoad, apiScriptVersionToLoad) {
                    var _a;
                    this.tab = tab, this.id = null !== (_a = this.tab.id) && void 0 !== _a ? _a : 0, 
                    this.contentScriptPath = `scripts/content.v${contentScriptVersionToLoad}.js`, this.apiScriptPath = `scripts/api.v${apiScriptVersionToLoad}.js`;
                }
                dispose() {
                    logger_1.Logger.log("Disposed tab", this.tab.id);
                }
                execute(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return logger_1.Logger.groupLoggingAsync((() => __awaiter(this, void 0, void 0, (function*() {
                            switch (request.name) {
                              case "GetAncestorListRequest":
                                return this.getAncestorList(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetElementFromPointRequest":
                                return this.getElementFromPoint(request);

                              case "GetElementRectangleRequest":
                                return this.getElementRectangle(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetElementRequest":
                              case "GetPreviousSiblingRequest":
                              case "GetNextSiblingRequest":
                                return this.getElement(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetChildrenRequest":
                                return this.getChildren(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "GetFocusedElementRequest":
                                return this.getFocusedElement(request);

                              case "GetIndexOfElementRequest":
                                return this.getIndexOfElement(request);

                              case "GetParentRequest":
                                return this.getParent(TabApi.validateCssSelectorContentScriptRequest(request));

                              case "InitiateDataExtractionRequest":
                                return this.initiateDataExtraction(request);

                              case "GetExtractionResultRequest":
                                return this.getExtractionResult(request);

                              case "SmartSearchTextRequest":
                                return this.anyFrameReturnsTrue(request);

                              case "PreparePageForExtractionRequest":
                              case "ResetUniverseRequest":
                              case "RevertPermanentHighlightingOfCurrentElementsRequest":
                              case "SetAttributeAllRequest":
                              case "GetAttributeSetAllRequest":
                                return this.allFramesReturnTrue(request);

                              case "TestSelectorRequest":
                                return this.testSelector(request);

                              default:
                                return this.defaultHandler(request);
                            }
                        }))), "Handling for request: ", request);
                    }));
                }
                defaultHandler(request) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (null !== (_a = request.frameId) && void 0 !== _a || (request.frameId = frame_1.Frame.MainFrame), 
                        TabApi.isValidCssSelectorContentScriptRequest(request)) {
                            const cssSelectorRequest = request, cssSelector = cssSelectorRequest.parameters.cssSelectorPerFrame.pop(), frame = yield this.findSubFrameBySelectors(request.requestId, cssSelectorRequest.parameters.cssSelectorPerFrame);
                            if (!frame) throw new Error("Frame is not available.");
                            request.frameId = frame.id, request.parameters.cssSelector = cssSelector, request.parameters.cssSelectorPerFrame = void 0;
                        }
                        return this.sendMessage(request);
                    }));
                }
                testSelector(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let frame = yield this.getFrame(frame_1.Frame.MainFrame), nodesFound = 0, result = null;
                        const selectorsPerFrame = null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : [];
                        for (let i = 0; i < selectorsPerFrame.length; i++) {
                            request.parameters.cssSelector = selectorsPerFrame[i], request.parameters.selectorElements = request.parameters.selectorElementsPerFrame[i], 
                            request.parameters.cssSelectorPerFrame = void 0, request.frameId = null == frame ? void 0 : frame.id;
                            const response = yield this.defaultHandler(request);
                            if (null == response || response.error) return response;
                            if (0 === response.result.elementsMatched) return response.result.elementNodesMatched += nodesFound, 
                            response;
                            result = response, nodesFound += response.result.elementNodesMatched, frame = yield this.findSubFrameBySelector(request.requestId, selectorsPerFrame[i], frame);
                        }
                        return null !== result && (result.result.elementNodesMatched = nodesFound), result;
                    }));
                }
                allFramesReturnTrue(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        for (const frame of yield this.getAllFrames()) {
                            request.frameId = null == frame ? void 0 : frame.id;
                            const response = yield this.defaultHandler(request);
                            if (null == response || void 0 !== response.error || !response.result) return new response_1.Response(request, !1, null == response ? void 0 : response.error);
                        }
                        return new response_1.Response(request, !0);
                    }));
                }
                anyFrameReturnsTrue(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        for (const frame of yield this.getAllFrames()) {
                            request.frameId = null == frame ? void 0 : frame.id;
                            const response = yield this.defaultHandler(request);
                            if (null == response || void 0 !== response.error) return new response_1.Response(request, !1, null == response ? void 0 : response.error);
                            if (response.result) return new response_1.Response(request, !0);
                        }
                        return new response_1.Response(request, !1);
                    }));
                }
                extractHandpickedData(request) {
                    var _a, _b, _c;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let result = [];
                        const selectors = Array.from(null !== (_c = null === (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.parameters) || void 0 === _b ? void 0 : _b.selectors) && void 0 !== _c ? _c : []);
                        for (const selector of selectors) {
                            const response = yield this.defaultHandler({
                                name: request.name,
                                requestId: crypto.randomUUID(),
                                tabId: request.tabId,
                                parameters: {
                                    cssSelectorPerFrame: selector.frameSelectors,
                                    isDesignTime: request.parameters.isDesignTime,
                                    parameters: {
                                        selectors: [ {
                                            selector: selector.frameSelectors[selector.frameSelectors.length - 1],
                                            attribute: selector.attribute
                                        } ]
                                    },
                                    type: request.parameters.type
                                }
                            });
                            result = result.concat(response.result);
                        }
                        return result;
                    }));
                }
                getAncestorList(request) {
                    var _a, _b, _c, _d, _e;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let frame = null, resultCollection = [], selector = null;
                        const frameSelectors = null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : [];
                        for (const frameSelector of frameSelectors) {
                            request.parameters = {
                                cssSelector: frameSelector,
                                cssSelectorPerFrame: void 0
                            };
                            const response = yield this.defaultHandler(request);
                            if (null == response || response.error || void 0 === response.result || null === response.result || 0 === response.result.length) break;
                            null !== selector && response.result.forEach((element => element.cssSelectorString = `${selector} > ${element.cssSelectorString}`));
                            const lastElement = response.result[response.result.length - 1];
                            if (selector = lastElement.cssSelectorString, resultCollection = resultCollection.concat(response.result), 
                            "iframe" !== (null === (_c = lastElement.tag) || void 0 === _c ? void 0 : _c.toLowerCase()) && "frame" !== (null === (_d = lastElement.tag) || void 0 === _d ? void 0 : _d.toLowerCase())) break;
                            frame = yield this.findSubFrameBySelector(request.requestId, frameSelector, frame), 
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return "html" === (null === (_e = resultCollection[0].tag) || void 0 === _e ? void 0 : _e.toLowerCase()) && resultCollection.shift(), 
                        new response_1.Response(request, resultCollection);
                    }));
                }
                getChildren(request) {
                    var _a, _b, _c, _d, _e, _f;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const frameSelectors = Array.from(null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : []), element = yield this.defaultHandler({
                            name: "GetElementRequest",
                            requestId: request.requestId,
                            parameters: {
                                cssSelector: null === (_c = request.parameters) || void 0 === _c ? void 0 : _c.cssSelector,
                                cssSelectorPerFrame: [ ...frameSelectors ]
                            },
                            tabId: this.id
                        }), elementTag = null === (_e = null === (_d = null == element ? void 0 : element.result) || void 0 === _d ? void 0 : _d.tag) || void 0 === _e ? void 0 : _e.toLowerCase();
                        if ("iframe" === elementTag || "frame" === elementTag) {
                            const frame = yield this.findSubFrameBySelectors(request.requestId, null === (_f = request.parameters) || void 0 === _f ? void 0 : _f.cssSelectorPerFrame), htmlElement = yield this.defaultHandler({
                                name: "GetElementRequest",
                                requestId: request.requestId,
                                frameId: frame.id,
                                parameters: {
                                    cssSelector: "html"
                                },
                                tabId: this.id
                            });
                            return null == htmlElement || htmlElement.error ? new response_1.Response(request, null, null == htmlElement ? void 0 : htmlElement.error) : (htmlElement.result.cssSelectorString = `${frameSelectors.join(" > ")} > ${htmlElement.result.cssSelectorString}`, 
                            new response_1.Response(request, [ htmlElement.result ]));
                        }
                        const response = yield this.defaultHandler(request);
                        if (null == response) return response;
                        if (void 0 !== response.result && null !== response.result) {
                            frameSelectors.pop();
                            const children = response.result.map((c => (c.cssSelectorString = [ ...frameSelectors, c.cssSelectorString ].join(" > "), 
                            c)));
                            return new response_1.Response(request, children);
                        }
                        return response;
                    }));
                }
                getElementFromPoint(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let x = 0, y = 0, selector = null, frame = null, result = null;
                        for (;;) {
                            const message = yield this.defaultHandler(request), response = message;
                            if (null == response || response.error) return message;
                            result = response.result;
                            const offsetX = result.rectangleProperties.elementOffsetLeft - result.rectangleProperties.viewPortScrollLeft, offsetY = result.rectangleProperties.elementOffsetTop - result.rectangleProperties.viewPortScrollTop;
                            if (x += offsetX, y += offsetY, selector = null === selector ? result.cssSelectorString : `${selector} > ${result.cssSelectorString}`, 
                            "iframe" !== (null === (_a = result.tag) || void 0 === _a ? void 0 : _a.toLowerCase()) && "frame" !== (null === (_b = result.tag) || void 0 === _b ? void 0 : _b.toLowerCase())) break;
                            if (request.parameters.x -= offsetX + result.rectangleProperties.paddingLeft, request.parameters.y -= offsetY + result.rectangleProperties.paddingTop, 
                            frame = yield this.findSubFrameBySelector(request.requestId, result.cssSelectorString, frame), 
                            null === frame) break;
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return result.rectangleProperties.elementOffsetLeft = x, result.rectangleProperties.elementOffsetTop = y, 
                        result.cssSelectorString = selector, new response_1.Response(request, result);
                    }));
                }
                getElement(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const frameSelectors = Array.from(null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : []);
                        frameSelectors.pop();
                        const response = yield this.defaultHandler(request);
                        return null == response ? response : void 0 !== response.result && null !== response.result ? (frameSelectors.push(response.result.cssSelectorString), 
                        response.result.cssSelectorString = frameSelectors.join(" > "), response) : response;
                    }));
                }
                getElementRectangle(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let x = 0, y = 0, frame = null, result = null;
                        const frameSelectors = null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : [];
                        for (const frameSelector of frameSelectors) {
                            request.parameters = {
                                cssSelector: frameSelector,
                                cssSelectorPerFrame: void 0
                            };
                            const response = yield this.defaultHandler(request);
                            if (null == response || response.error) return new response_1.Response(request, null, null == response ? void 0 : response.error);
                            result = response.result, x += result.elementOffsetLeft, y += result.elementOffsetTop, 
                            frameSelectors.indexOf(frameSelector) !== frameSelectors.length - 1 && (x -= result.viewPortScrollLeft - result.paddingLeft, 
                            y -= result.viewPortScrollTop - result.paddingTop), frame = yield this.findSubFrameBySelector(request.requestId, frameSelector, frame), 
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return null !== result && (result.elementOffsetLeft = x, result.elementOffsetTop = y), 
                        new response_1.Response(request, result);
                    }));
                }
                getExtractionResult(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return new Promise(((resolve, _rejected) => {
                            resolve(new response_1.Response(request, this.extractionResult));
                        }));
                    }));
                }
                getFocusedElement(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        let x = 0, y = 0, selector = null, frame = null, result = null;
                        for (;;) {
                            const message = yield this.defaultHandler(request), response = message;
                            if (null == response || response.error) return message;
                            if (result = response.result, x += result.rectangleProperties.elementOffsetLeft - result.rectangleProperties.viewPortScrollLeft, 
                            y += result.rectangleProperties.elementOffsetTop - result.rectangleProperties.viewPortScrollTop, 
                            selector = null === selector ? result.cssSelectorString : `${selector} > ${result.cssSelectorString}`, 
                            "iframe" !== (null === (_a = result.tag) || void 0 === _a ? void 0 : _a.toLowerCase()) && "frame" !== (null === (_b = result.tag) || void 0 === _b ? void 0 : _b.toLowerCase())) break;
                            if (frame = yield this.findSubFrameBySelector(request.requestId, result.cssSelectorString, frame), 
                            null === frame) break;
                            request.frameId = null == frame ? void 0 : frame.id;
                        }
                        return result.rectangleProperties.elementOffsetLeft = x, result.rectangleProperties.elementOffsetTop = y, 
                        result.cssSelectorString = selector, new response_1.Response(request, result);
                    }));
                }
                getIndexOfElement(request) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const parameters = request.parameters;
                        return parameters.specificElementCssSelector = null === (_a = parameters.specificElementCssSelectorPerFrame) || void 0 === _a ? void 0 : _a.pop(), 
                        parameters.specificElementCssSelectorPerFrame = void 0, this.defaultHandler(request);
                    }));
                }
                getParent(request) {
                    var _a, _b;
                    return __awaiter(this, void 0, void 0, (function*() {
                        const frameSelectors = Array.from(null !== (_b = null === (_a = request.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && void 0 !== _b ? _b : []);
                        frameSelectors.pop();
                        const response = yield this.defaultHandler(request);
                        return null == response ? response : void 0 !== response.result && null !== response.result ? (frameSelectors.push(response.result.cssSelectorString), 
                        response.result.cssSelectorString = frameSelectors.join(" > "), response) : frameSelectors.length > 0 ? (request.parameters = {
                            cssSelector: frameSelectors[frameSelectors.length - 1],
                            cssSelectorPerFrame: frameSelectors
                        }, request.name = "GetElementRequest", this.defaultHandler(request)) : response;
                    }));
                }
                initiateDataExtraction(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return this.extractionResult = extraction_result_1.ExtractionResult.pending(), setTimeout((() => __awaiter(this, void 0, void 0, (function*() {
                            var _a;
                            try {
                                if (TabApi.isValidExtractHandpickedValuesRequest(request)) return void (this.extractionResult = extraction_result_1.ExtractionResult.complete(yield this.extractHandpickedData(request)));
                                if (TabApi.isValidCssSelectorContentScriptRequest(request)) return void (this.extractionResult = extraction_result_1.ExtractionResult.complete(null === (_a = yield this.defaultHandler(request)) || void 0 === _a ? void 0 : _a.result));
                                this.extractionResult = extraction_result_1.ExtractionResult.error("InitiateDataExtractionRequest is not in valid format.");
                            } catch (e) {
                                this.extractionResult = extraction_result_1.ExtractionResult.error(e.toString());
                            }
                        }))), 0), new Promise(((resolve, _rejected) => {
                            resolve(new response_1.Response(request, !0));
                        }));
                    }));
                }
                getPort(frameId) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const $frame = yield this.getFrame(frameId);
                        if (!$frame || $frame.id !== frameId || !(0, can_scripts_be_injected_1.canScriptsBeInjected)($frame.url)) return null;
                        if (!($frame.isMain() ? yield this.injectScriptsToMainFrame() : yield this.injectScriptsToSubFrame($frame.id))) return null;
                        const port = chrome.tabs.connect(this.id, {
                            frameId
                        });
                        return port || (logger_1.Logger.warn(`Port to frame '${frameId}' at tab '${this.id}' could not be created.`), 
                        null);
                    }));
                }
                injectScriptsToMainFrame() {
                    return __awaiter(this, void 0, void 0, (function*() {
                        try {
                            return (yield chrome.scripting.executeScript({
                                target: {
                                    tabId: this.id,
                                    frameIds: [ frame_1.Frame.MainFrame ]
                                },
                                func: () => globalThis._padScriptLoaded_E2C4773F
                            }))[0].result || (logger_1.Logger.log("Injecting scripts to main frame at tab: ", this.id), 
                            yield chrome.scripting.executeScript({
                                target: {
                                    tabId: this.id,
                                    frameIds: [ frame_1.Frame.MainFrame ]
                                },
                                files: [ this.contentScriptPath, this.apiScriptPath ]
                            }), logger_1.Logger.log("Injected scripts to main frame at tab: ", this.id)), !0;
                        } catch (e) {
                            throw logger_1.Logger.error("Unable to inject scripts to main frame at tab: ", this.id, " with exception", e.message), 
                            new unableToInjectScriptsError_1.UnableToInjectScriptsError(e.message);
                        }
                    }));
                }
                injectScriptsToSubFrame(frameId) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const tab = this;
                        return (0, execute_with_timeout_1.executeWithTimeout)(TabApi.injectionTimeOut, function() {
                            return __awaiter(this, void 0, void 0, (function*() {
                                try {
                                    return (yield chrome.scripting.executeScript({
                                        target: {
                                            tabId: tab.id,
                                            frameIds: [ frameId ]
                                        },
                                        func: () => globalThis._padScriptLoaded_E2C4773F
                                    }))[0].result || (logger_1.Logger.log("Injecting scripts to frame: ", frameId, " at tab: ", tab.id), 
                                    yield chrome.scripting.executeScript({
                                        target: {
                                            tabId: tab.id,
                                            frameIds: [ frameId ]
                                        },
                                        files: [ tab.contentScriptPath, tab.apiScriptPath ]
                                    }), logger_1.Logger.log("Injected scripts to frame: ", frameId, " at tab: ", tab.id)), 
                                    !0;
                                } catch (e) {
                                    return logger_1.Logger.error("Unable to inject scripts to frame: ", frameId, " at tab: ", tab.id, " with exception", e.message), 
                                    !1;
                                }
                            }));
                        }(), !1);
                    }));
                }
                sendMessage(message) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const messagePort = yield this.getPort(message.frameId);
                        return new Promise(((resolve, reject) => {
                            const onMessage = m => {
                                logger_1.Logger.log("Received Message: ", m), m.requestId === message.requestId && (removeHandlers(), 
                                resolve(m), messagePort.disconnect());
                            }, onDisconnect = _ => {
                                logger_1.Logger.error("Port disconnected: ", message), removeHandlers(), reject("Port disconnected");
                            }, removeHandlers = () => {
                                messagePort.onMessage.removeListener(onMessage), messagePort.onDisconnect.removeListener(onDisconnect);
                            };
                            messagePort.onMessage.addListener(onMessage), messagePort.onDisconnect.addListener(onDisconnect);
                            try {
                                logger_1.Logger.log("Sending message to tab:", this.id, "and frame:", message.frameId, message), 
                                messagePort.postMessage(message);
                            } catch (e) {
                                logger_1.Logger.error("Failed to post message: ", message, e), messagePort.disconnect(), 
                                removeHandlers(), reject(e);
                            }
                        }));
                    }));
                }
                getAllFrames() {
                    return new Promise(((resolve, rejected) => {
                        chrome.webNavigation.getAllFrames({
                            tabId: this.id
                        }, (frames => {
                            null == frames || frames.length <= 0 ? rejected("No frames were returned.") : resolve(frames.map((frame => new frame_1.Frame({
                                id: frame.frameId,
                                tabId: this.id,
                                parentFrameId: frame.parentFrameId,
                                url: frame.url
                            }))));
                        }));
                    }));
                }
                getFrame(frameId) {
                    return new Promise(((resolve, rejected) => {
                        chrome.webNavigation.getFrame({
                            tabId: this.id,
                            frameId
                        }, (frame => {
                            frame ? resolve(new frame_1.Frame({
                                id: frameId,
                                tabId: this.id,
                                parentFrameId: frame.parentFrameId,
                                url: frame.url
                            })) : rejected("No frame was returned.");
                        }));
                    }));
                }
                findSubFrameBySelector(requestId, selector, currentFrame) {
                    var _a;
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (null != currentFrame || (currentFrame = yield this.getFrame(frame_1.Frame.MainFrame)), 
                        !currentFrame) return null;
                        if (selector.toLowerCase().indexOf("frame") <= -1) return currentFrame;
                        const response = yield this.defaultHandler({
                            name: "GetIndexOfFrameRequest",
                            requestId,
                            frameId: currentFrame.id,
                            parameters: {
                                cssSelector: selector
                            },
                            tabId: this.id
                        });
                        if ((null == response ? void 0 : response.requestId) !== requestId) return null;
                        if (void 0 === (null == response ? void 0 : response.result) || null === (null == response ? void 0 : response.result) || response.error) return (null === (_a = null == response ? void 0 : response.error) || void 0 === _a ? void 0 : _a.errorCode) === TabApi.noframeErrorCode ? currentFrame : null;
                        for (const frame of yield this.getAllFrames()) if (frame.parentFrameId === currentFrame.id && (yield frame.isAt(response.result))) return frame;
                        return null;
                    }));
                }
                findSubFrameBySelectors(requestId, selectors) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        let currentFrame = yield this.getFrame(frame_1.Frame.MainFrame);
                        if (!currentFrame) return null;
                        for (const selector of selectors) if (currentFrame = yield this.findSubFrameBySelector(requestId, selector, currentFrame), 
                        null == currentFrame) break;
                        return currentFrame;
                    }));
                }
                static validateCssSelectorContentScriptRequest(request) {
                    if (!TabApi.isValidCssSelectorContentScriptRequest(request)) throw logger_1.Logger.error("Message is not CssSelectorContentScriptRequest", request), 
                    new Error("Request is not CssSelectorContentScriptRequest");
                    return request;
                }
                static isValidCssSelectorContentScriptRequest(request) {
                    var _a, _b;
                    const cssSelectorContentScriptRequest = request;
                    return void 0 !== (null === (_a = cssSelectorContentScriptRequest.parameters) || void 0 === _a ? void 0 : _a.cssSelectorPerFrame) && null !== (null === (_b = cssSelectorContentScriptRequest.parameters) || void 0 === _b ? void 0 : _b.cssSelectorPerFrame) && cssSelectorContentScriptRequest.parameters.cssSelectorPerFrame.length > 0;
                }
                static isValidExtractHandpickedValuesRequest(request) {
                    var _a, _b, _c, _d, _e;
                    const extractDataContentScriptRequest = request;
                    return void 0 !== (null === (_b = null === (_a = null == extractDataContentScriptRequest ? void 0 : extractDataContentScriptRequest.parameters) || void 0 === _a ? void 0 : _a.parameters) || void 0 === _b ? void 0 : _b.selectors) && null !== (null === (_d = null === (_c = null == extractDataContentScriptRequest ? void 0 : extractDataContentScriptRequest.parameters) || void 0 === _c ? void 0 : _c.parameters) || void 0 === _d ? void 0 : _d.selectors) && (null === (_e = null == extractDataContentScriptRequest ? void 0 : extractDataContentScriptRequest.parameters) || void 0 === _e ? void 0 : _e.parameters.selectors.length) > 0;
                }
            }
            exports.TabApi = TabApi, TabApi.injectionTimeOut = 500, TabApi.noframeErrorCode = 11;
        },
        56549: function(__unused_webpack_module, exports, __webpack_require__) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.BackgroundV3 = void 0;
            __webpack_require__(17967);
            const logger_1 = __webpack_require__(88901), window_removed_notification_1 = __webpack_require__(1009), window_focused_changed_notification_1 = __webpack_require__(52253), window_created_notification_1 = __webpack_require__(1875), tab_api_1 = __webpack_require__(90738), can_scripts_be_injected_1 = __webpack_require__(9805), execute_with_timeout_1 = __webpack_require__(87555);
            class BackgroundV3 {
                constructor(communicatorToNative, contentScriptVersionToLoad, apiScriptVersionToLoad) {
                    this.communicatorToNative = communicatorToNative, this.contentScriptVersionToLoad = contentScriptVersionToLoad, 
                    this.apiScriptVersionToLoad = apiScriptVersionToLoad, this.tabs = {}, this.registerChromeEvents(), 
                    this.registerHostEvents(), logger_1.Logger.log("Background script V3 loaded");
                }
                static onGetTab(request) {
                    return chrome.tabs.get(request.tabId);
                }
                static onGetAllWindows() {
                    return chrome.windows.getAll({
                        populate: !0,
                        windowTypes: [ "normal" ]
                    });
                }
                static onGetAllTabs(request) {
                    return chrome.tabs.query({
                        windowId: request.windowId
                    });
                }
                static onActivateTab(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.update(request.tabId, {
                            active: !0
                        }), !0;
                    }));
                }
                static onRefreshPage(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.reload(request.tabId, {
                            bypassCache: !0
                        }), !0;
                    }));
                }
                static onNavigateToUrl(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const url = request.url;
                        return yield chrome.tabs.update(request.tabId, {
                            url
                        }), !0;
                    }));
                }
                static onCreateNewTab(request) {
                    const url = request.url;
                    return chrome.tabs.create({
                        url
                    });
                }
                static onCloseTab(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.remove(request.tabId), !0;
                    }));
                }
                static onClearCookies(_) {
                    return new Promise((p => chrome.browsingData.removeCookies({}, (() => p(!0)))));
                }
                static onClearCache(_) {
                    return new Promise((p => chrome.browsingData.removeCache({}, (() => p(!0)))));
                }
                static onSetZoom(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return yield chrome.tabs.setZoom(request.tabId, request.zoom), !0;
                    }));
                }
                static onGetZoom(request) {
                    return chrome.tabs.getZoom(request.tabId);
                }
                static onIsIeMode(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        return (0, execute_with_timeout_1.executeWithTimeout)(100, function() {
                            var _a;
                            return __awaiter(this, void 0, void 0, (function*() {
                                try {
                                    return yield chrome.scripting.executeScript({
                                        target: {
                                            tabId: request.tabId
                                        },
                                        func: () => !0
                                    }), !1;
                                } catch (e) {
                                    return !0 === (null === (_a = e.message) || void 0 === _a ? void 0 : _a.startsWith("Frame with ID"));
                                }
                            }));
                        }(), !1);
                    }));
                }
                static onRunJavaScript(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        if (!(yield BackgroundV3.attachDebuggerIfNeeded(request.tabId))) throw new Error("Can't attach debugger");
                        return new Promise((resolve => {
                            chrome.debugger.sendCommand({
                                tabId: request.tabId
                            }, "Runtime.evaluate", {
                                expression: request.code
                            }, (result => {
                                chrome.debugger.detach({
                                    tabId: request.tabId
                                }, (() => {
                                    var _a;
                                    resolve(`${null !== (_a = result.result.value) && void 0 !== _a ? _a : result.result}`);
                                }));
                            }));
                        }));
                    }));
                }
                removeTab(tabId) {
                    this.tabs[tabId] && (logger_1.Logger.log("Tab removed: ", this.tabs[tabId]), this.tabs[tabId].dispose(), 
                    delete this.tabs[tabId]);
                }
                static attachDebuggerIfNeeded(tabId) {
                    return new Promise((resolve => chrome.debugger.getTargets((targets => {
                        for (let i = 0; i < targets.length; i++) if (targets[i].tabId === tabId) return targets[i].attached ? void resolve(!1) : void chrome.debugger.attach({
                            tabId
                        }, "1.2", (() => {
                            resolve(!0);
                        }));
                        resolve(!1);
                    }))));
                }
                dispose() {
                    this.unRegisterChromeEvents(), this.unRegisterHostEvents(), Object.keys(this.tabs).forEach((key => {
                        this.tabs[key].dispose(), delete this.tabs[key];
                    })), this.tabs = void 0, logger_1.Logger.log("Background script V3 unloaded");
                }
                defaultHandler(request) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        const $tab = yield chrome.tabs.get(request.tabId);
                        if ($tab && (0, can_scripts_be_injected_1.canScriptsBeInjected)($tab.url)) return void 0 !== this.tabs[request.tabId] && null !== this.tabs[request.tabId] || (this.tabs[request.tabId] = new tab_api_1.TabApi($tab, this.contentScriptVersionToLoad, this.apiScriptVersionToLoad)), 
                        this.tabs[request.tabId].execute(request);
                    }));
                }
                registerHostEvents() {
                    this.communicatorToNative.on("GetTabRequest", (m => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV3.onGetTab(m.parameters);
                    })))), this.communicatorToNative.on("GetAllWindowsRequest", (() => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV3.onGetAllWindows();
                    })))), this.communicatorToNative.on("GetAllTabsRequest", (m => __awaiter(this, void 0, void 0, (function*() {
                        return BackgroundV3.onGetAllTabs(m.parameters);
                    })))), this.communicatorToNative.on("ActivateTabRequest", (m => BackgroundV3.onActivateTab(m.parameters))), 
                    this.communicatorToNative.on("RefreshPageRequest", (m => BackgroundV3.onRefreshPage(m.parameters))), 
                    this.communicatorToNative.on("NavigateToUrlRequest", (m => BackgroundV3.onNavigateToUrl(m.parameters))), 
                    this.communicatorToNative.on("CreateNewTabRequest", (m => BackgroundV3.onCreateNewTab(m.parameters))), 
                    this.communicatorToNative.on("CloseTabRequest", (m => BackgroundV3.onCloseTab(m.parameters))), 
                    this.communicatorToNative.on("ClearCookiesRequest", (m => BackgroundV3.onClearCookies(m))), 
                    this.communicatorToNative.on("ClearCacheRequest", (m => BackgroundV3.onClearCache(m))), 
                    this.communicatorToNative.on("SetZoomRequest", (m => BackgroundV3.onSetZoom(m.parameters))), 
                    this.communicatorToNative.on("GetZoomRequest", (m => BackgroundV3.onGetZoom(m.parameters))), 
                    this.communicatorToNative.on("IsIEModeTabRequest", (m => BackgroundV3.onIsIeMode(m.parameters))), 
                    this.communicatorToNative.on("RunJavaScriptRequest", (m => BackgroundV3.onRunJavaScript(m.parameters))), 
                    this.communicatorToNative.addDefaultHandler((m => this.defaultHandler(BackgroundV3.validateContentScriptRequest(m))));
                }
                unRegisterHostEvents() {
                    this.communicatorToNative.removeHandler("GetTabRequest"), this.communicatorToNative.removeHandler("GetAllWindowsRequest"), 
                    this.communicatorToNative.removeHandler("GetAllTabsRequest"), this.communicatorToNative.removeHandler("ActivateTabRequest"), 
                    this.communicatorToNative.removeHandler("RefreshPageRequest"), this.communicatorToNative.removeHandler("NavigateToUrlRequest"), 
                    this.communicatorToNative.removeHandler("CreateNewTabRequest"), this.communicatorToNative.removeHandler("CloseTabRequest"), 
                    this.communicatorToNative.removeHandler("ClearCookiesRequest"), this.communicatorToNative.removeHandler("ClearCacheRequest"), 
                    this.communicatorToNative.removeHandler("SetZoomRequest"), this.communicatorToNative.removeHandler("GetZoomRequest"), 
                    this.communicatorToNative.removeHandler("IsIEModeTabRequest"), this.communicatorToNative.removeHandler("RunJavaScriptRequest");
                }
                onWindowCreated(window) {
                    var _a;
                    console.log(`Window created. WindowId: ${window.id}`), this.communicatorToNative.post(new window_created_notification_1.WindowCreatedNotification(null !== (_a = window.id) && void 0 !== _a ? _a : 0));
                }
                onWindowFocusChanged(windowId) {
                    windowId !== chrome.windows.WINDOW_ID_NONE && (console.log(`Window focused. WindowId: ${windowId}`), 
                    this.communicatorToNative.post(new window_focused_changed_notification_1.WindowFocusedChangedNotification(windowId)));
                }
                onWindowRemoved(windowId) {
                    console.log(`Window removed. WindowId: ${windowId}`), this.communicatorToNative.post(new window_removed_notification_1.WindowRemovedNotification(windowId));
                }
                unRegisterChromeEvents() {
                    chrome.windows.onCreated.removeListener(this.onWindowCreatedCallback), chrome.windows.onFocusChanged.removeListener(this.onWindowFocusChangedCallback), 
                    chrome.windows.onRemoved.removeListener(this.onWindowRemovedCallback), chrome.tabs.onRemoved.removeListener(this.onTabRemovedCallback);
                }
                registerChromeEvents() {
                    const script = this;
                    this.onWindowCreatedCallback = window => script.onWindowCreated(window), this.onWindowFocusChangedCallback = windowId => script.onWindowFocusChanged(windowId), 
                    this.onWindowRemovedCallback = windowId => script.onWindowRemoved(windowId), this.onTabRemovedCallback = (tabId, _) => script.removeTab(tabId), 
                    chrome.windows.onCreated.addListener(this.onWindowCreatedCallback), chrome.windows.onFocusChanged.addListener(this.onWindowFocusChangedCallback), 
                    chrome.windows.onRemoved.addListener(this.onWindowRemovedCallback), chrome.tabs.onRemoved.addListener(this.onTabRemovedCallback);
                }
                static validateContentScriptRequest(request) {
                    const contentScript = request;
                    if (null == contentScript || void 0 === contentScript.tabId || null === contentScript.tabId) throw logger_1.Logger.error("Message is not ContentScriptRequest", request), 
                    new Error("Request is not ContentScriptRequest");
                    return contentScript;
                }
            }
            exports.BackgroundV3 = BackgroundV3;
        },
        66042: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Notification = void 0;
            exports.Notification = class {
                constructor(notify) {
                    this.notify = notify, this.name = "notify", this.requestId = "";
                }
            };
        },
        1875: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowCreatedNotification = void 0;
            const notification_1 = __webpack_require__(66042);
            class WindowCreatedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_created"), this.windowId = windowId;
                }
            }
            exports.WindowCreatedNotification = WindowCreatedNotification;
        },
        52253: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowFocusedChangedNotification = void 0;
            const notification_1 = __webpack_require__(66042);
            class WindowFocusedChangedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_focused"), this.windowId = windowId;
                }
            }
            exports.WindowFocusedChangedNotification = WindowFocusedChangedNotification;
        },
        1009: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.WindowRemovedNotification = void 0;
            const notification_1 = __webpack_require__(66042);
            class WindowRemovedNotification extends notification_1.Notification {
                constructor(windowId) {
                    super("window_removed"), this.windowId = windowId;
                }
            }
            exports.WindowRemovedNotification = WindowRemovedNotification;
        },
        9805: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.canScriptsBeInjected = void 0, exports.canScriptsBeInjected = function(url) {
                return null != url && !url.startsWith("chrome://") && !url.startsWith("edge://");
            };
        },
        87555: (__unused_webpack_module, exports) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.executeWithTimeout = void 0, exports.executeWithTimeout = function(timeoutInMs, method, valueOnTimeOut) {
                return Promise.race([ method, new Promise((resolve => {
                    setTimeout((() => {
                        resolve(valueOnTimeOut);
                    }), timeoutInMs);
                })) ]);
            };
        },
        88901: function(__unused_webpack_module, exports) {
            var __awaiter = this && this.__awaiter || function(thisArg, _arguments, P, generator) {
                return new (P || (P = Promise))((function(resolve, reject) {
                    function fulfilled(value) {
                        try {
                            step(generator.next(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function rejected(value) {
                        try {
                            step(generator.throw(value));
                        } catch (e) {
                            reject(e);
                        }
                    }
                    function step(result) {
                        var value;
                        result.done ? resolve(result.value) : (value = result.value, value instanceof P ? value : new P((function(resolve) {
                            resolve(value);
                        }))).then(fulfilled, rejected);
                    }
                    step((generator = generator.apply(thisArg, _arguments || [])).next());
                }));
            };
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.Logger = void 0;
            class Logger {
                static enable() {
                    try {
                        (null !== globalThis && void 0 !== globalThis ? globalThis : window).padLoggerEnabled = !0, 
                        console.log("Logger is enabled");
                    } catch (e) {
                        console.error("Error during enabling logger", e);
                    }
                }
                static disable() {
                    try {
                        (null !== globalThis && void 0 !== globalThis ? globalThis : window).padLoggerEnabled = !1, 
                        console.log("Logger is disabled");
                    } catch (e) {
                        console.error("Error during disabling logger", e);
                    }
                }
                static log(...data) {
                    Logger.isEnabled() && console.log(...data);
                }
                static group(...label) {
                    Logger.isEnabled() && console.group(...label);
                }
                static groupEnd() {
                    Logger.isEnabled() && console.groupEnd();
                }
                static error(...data) {
                    Logger.isEnabled() && console.error(...data);
                }
                static warn(...data) {
                    Logger.isEnabled() && console.warn(...data);
                }
                static groupLogging(callback, ...label) {
                    Logger.group(...label);
                    try {
                        callback();
                    } finally {
                        Logger.groupEnd();
                    }
                }
                static groupLoggingAsync(callback, ...label) {
                    return __awaiter(this, void 0, void 0, (function*() {
                        Logger.group(...label);
                        try {
                            return yield callback();
                        } finally {
                            Logger.groupEnd();
                        }
                    }));
                }
                static isEnabled() {
                    var _a;
                    try {
                        return null !== (_a = (null !== globalThis && void 0 !== globalThis ? globalThis : window).padLoggerEnabled) && void 0 !== _a && _a;
                    } catch (e) {
                        return console.error("Error during checking if logger is enabled", e), !0;
                    }
                }
            }
            exports.Logger = Logger;
        },
        92025: (__unused_webpack_module, exports, __webpack_require__) => {
            Object.defineProperty(exports, "__esModule", {
                value: !0
            }), exports.setBrowserApi = void 0;
            __webpack_require__(88901);
            exports.setBrowserApi = function() {
                0;
            };
        }
    }, __webpack_module_cache__ = {};
    (function __webpack_require__(moduleId) {
        var cachedModule = __webpack_module_cache__[moduleId];
        if (void 0 !== cachedModule) return cachedModule.exports;
        var module = __webpack_module_cache__[moduleId] = {
            exports: {}
        };
        return __webpack_modules__[moduleId].call(module.exports, module, module.exports, __webpack_require__), 
        module.exports;
    })(88069);
})();