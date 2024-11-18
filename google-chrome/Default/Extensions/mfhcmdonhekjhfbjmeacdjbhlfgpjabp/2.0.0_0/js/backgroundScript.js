'use strict';

const HALF_SECOND = 500;
const ONE_SECOND = 1000;
const ONE_MINUTE = 60 * ONE_SECOND;
const ONE_HOUR = 60 * ONE_MINUTE;
const ONE_DAY = 24 * ONE_HOUR;

(function () {
    const blacklistReady = new Promise((resolve, reject) => {
        setTimeout(function () {
            storageUtil.load("acsBlacklist", null, (data) => {
                if (data?.acsBlacklist.length > 0) {
                    resolve(data.acsBlacklist);
                } else {
                    resolve([]);
                }
            });
        }, ONE_SECOND);
    });

    blacklistReady.then((blacklist) => {
        chrome.declarativeNetRequest.getDynamicRules(previousRules => {
            const rules = [];
            if (previousRules.length === 0) {
                
                blacklist.forEach((domain, i) => {
                    rules.push({
                        "id": i + 1,
                        "priority": 1,
                        "action": { "type": "block" },
                        "condition": { "urlFilter": `||${domain}`, "resourceTypes": ["main_frame"] }
                    });
                });
            }

            

            chrome.declarativeNetRequest.updateDynamicRules({
                addRules: rules
            });
        });
    });

    // Schedule once per day to get blacklist from localstorage and update dynamic list
    setInterval(() => {
        blacklistReady.then((blacklist) => {
            
            const rules = [];

            chrome.declarativeNetRequest.getDynamicRules(previousRules => {
                let getLastDynamicId = previousRules.length;
                const newBlacklist = blacklist.filter(x => !previousRules.some(y => x === y.condition.urlFilter.replace('||', '')));
                
                
                newBlacklist.forEach((domain, i) => {
                    rules.push({
                        "id": getLastDynamicId + i + 1,
                        "priority": 1,
                        "action": { "type": "block" },
                        "condition": { "urlFilter": `||${domain}`, "resourceTypes": ["main_frame"] }
                    });
                });

                // const previousRuleIds = previousRules.map((rule) => {
                //     return rule.id;
                // });

                // const addNewRules = previousRules.map((rule) => {
                //     return rule ?? rule.action.type === "block";
                // });

                chrome.declarativeNetRequest.updateDynamicRules({
                    // removeRuleIds: previousRuleIds,
                    addRules: rules
                });

                
                
            });
        });
    }, ONE_DAY);
})();

(function () {
    // chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((ev) => {
    //     const msg = `Navigation blocked to ${ev.request.url} on tab ${ev.request.tabId}.`;
    //     
    // });

    chrome.webRequest.onBeforeRequest.addListener((details) => {
        const requestType = details.type;
        const baseUrl = details.url;
        if ( requestType === 'main_frame' ) {
            
            storageUtil.load("acsBlacklist", null, (data) => {
                if (data?.acsBlacklist.length > 0) {
                    const blacklist = data.acsBlacklist;
                    const composeUrl = new URL(baseUrl);
                    const domain = composeUrl.hostname.replace('www.', '');
                    const inBlacklist = !!blacklist.find(d => d === domain);
    
                    if (inBlacklist) {
                        const promiseSessionRules = new Promise((resolve, reject) => {
                            setTimeout(() => {
                                chrome.declarativeNetRequest.getSessionRules(sessionRules => {
                                    const findSessionRule = !!sessionRules.find(rule => rule.condition.urlFilter === `||${domain}`);
                                    resolve(findSessionRule);
                                });
                            }, HALF_SECOND);
                        });
    
                        const promiseDynamicRules = new Promise((resolve, reject) => {
                            setTimeout(() => {
                                chrome.declarativeNetRequest.getDynamicRules((dynamicRules) => {
                                    const findDynamicRule = !!dynamicRules.find(rule => rule.condition.urlFilter === `||${domain}` && rule.action.type === "block");
                                    resolve(findDynamicRule);
                                });
                            }, HALF_SECOND);
                        });
                        
                        Promise.all([promiseSessionRules, promiseDynamicRules]).then((result) => {
                            
                            
                            if ((result[0] === false && result[1] === true)) {
                                if (baseUrl) {
                                    chrome.tabs.update({ url: `/document-blocked.html?details=${baseUrl}` });
                                } else {
                                    chrome.tabs.update({ url: baseUrl });
                                }
                            }
                        }).catch((error) => {
                            
                        });
                        
                    }
                }
            });
        }
    },{ urls: ['http://*/*', 'https://*/*'] });

    // chrome.webNavigation.onBeforeNavigate.addListener((tab) => {
    //     
    //     const baseUrl = tab.url;

        

    //     // const loadingPageUrl = chrome.runtime.getURL('loading-page.html');
    //     // chrome.tabs.update({ url: loadingPageUrl });
        
    // }, { url: [{ schemes: ["http", "https"] }] });
})();

(function () {
    const randomInteger = (min, max) => {
        return Math.floor(Math.random() * (max - min + 1) + min)
    }

    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.message === "documentBlocked") {
            if (request.what === "temporarilyWhitelistDocument") {
                const domain = request.hostname.replace('www.', '');
                chrome.declarativeNetRequest.getSessionRules(sessionRules => {
                    const findSessionRule = !!sessionRules.find(rule => rule.condition.urlFilter === `||${domain}`);
                    if (!findSessionRule) {
                        chrome.declarativeNetRequest.updateSessionRules({
                            addRules: [{
                                "id": randomInteger(1, 999999999),
                                "action": { "type": "allow" },
                                "condition": { "urlFilter": `||${domain}`, "resourceTypes": ["main_frame"] }
                            }]
                        }, () => {
                            
                        });
                    }
                });
            }

            if (request.what === "permanentWhitelistDocument") {
                chrome.declarativeNetRequest.getDynamicRules((dynamicRules) => {
                    
                    const domain = request.hostname.replace('www.', '');
                    const findDynamicRule = dynamicRules.find(rule => rule.condition.urlFilter === `||${domain}`);
                    

                    if (findDynamicRule?.action?.type === "block") {
                        chrome.declarativeNetRequest.updateDynamicRules({
                            removeRuleIds: [findDynamicRule.id],
                            addRules: [{
                                "id": findDynamicRule.id,
                                "action": { "type": "allow" },
                                "condition": { "urlFilter": `||${domain}`, "resourceTypes": ["main_frame"] }
                            }]
                        }, () => {
                            
                        });
                    }
                });
            }

            return true;
        }

        if (request.message === "adaware-telemetry") {
            telemetry.sendMetaEvent(request.what, { action: request.data.action });

            if (request.data.action === "cont") {
                setTimeout(() => {
                    chrome.tabs.update({ url: request.url });
                }, ONE_SECOND);
            }

            return true;
        }

        if (request.message === "validateUrls") {
            
            const filteredUrls = adawareCloudService.filterUrlRequest(request.urls);
            sendResponse({ urls: filteredUrls });

            return true;
        }

        return true;
    });
})();