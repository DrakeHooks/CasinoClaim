'use strict';

(function () {
    const oneSecond = 1000;
    const oneMinute = 60 * oneSecond;
    const oneHour = 60 * oneMinute;
    const oneDay = 24 * oneHour;
    let lastPing;
    const currentVersion = chrome.runtime.getManifest().version;
    const browserEnvironment = new systemUtil.browserEnvironmentData();

    const WEBCOMPANION_ENDPOINT = "http://localhost:9007/webcompanion/extension/wsext/token";
    const UNINSTALL_URL = "https://webcompanion.com/ws/uninstall.html?";

    const getUrlParameterFromString = (url, name) => {
        name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
        let regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
        let results = regex.exec(url);
        return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
    }

    const sendDailyActivityData = (lastPingTime) => {
        const lastPingDate = new Date(lastPingTime);
        const currentPingDate = Date.now();
        const deltaMinutes = (currentPingDate - lastPingDate.getTime()) / oneMinute;
        

        const dailyActivityData = {
            LastCallbackDate: lastPingDate.toISOString()
        };

        adawareTelemetry.sendEventTrackingInfo("DailyActivity", dailyActivityData);
    };

    const onAllReady = () => {
        lastPing = Date.now();
        setInterval(() => {
            sendDailyActivityData(lastPing);
            lastPing = Date.now();
        }, oneDay);  
    };

    const onVersionReady = (lastVersion) => {
        if (lastVersion !== currentVersion) {
            storageUtil.save("version", currentVersion);
        }
    };

    const onStartupHandler = () => {
        storageUtil.load("startupTime", Date.now(), (fetched) => {
            
            if (Date.now() - fetched.startupTime > oneDay) { // if last startup time is greater than 24 hours
                sendDailyActivityData(fetched.startupTime);
            }
            storageUtil.save("startupTime", Date.now());
        });
    };

    const onFirstInstallHandler = () => {
        let externalData = {
            "CampaignID": config.configurationData.externalData.CampaignID || "",
            "CLID": config.configurationData.externalData.CLID || "",
            "PartnerID": config.configurationData.externalData.PartnerID || "",
            "sourceTraffic": config.configurationData.externalData.sourceTraffic || "",
            "OfferID": config.configurationData.externalData.OfferID || "",
            "MK": config.configurationData.externalData.MK || "",
            "IK": config.configurationData.externalData.IK || ""
        };

        const checkParameterUrl = () => {
            
            return new Promise((resolve, reject) => {
                try {
                    chrome.tabs.query({ url: "https://webcompanion.com/w*" }, (tabs) => {
                        if (tabs.length > 0) {
                            let url = tabs[0].url;
    
                            if ((url.split("?")).length > 1) {
                                externalData.PartnerID = getUrlParameterFromString(url, "partnerId") || config.configurationData.externalData.PartnerID;
                                externalData.CampaignID = getUrlParameterFromString(url, "utm_campaign");
                                externalData.sourceTraffic = getUrlParameterFromString(url, "sourceTraffic");
                                externalData.MK = getUrlParameterFromString(url, "mk");
                                externalData.IK = getUrlParameterFromString(url, "ik");
                            }
                            
                            resolve(externalData);
                        } else {
                            
                            resolve(externalData);
                        }
                    });
                } catch (err) {
                    
                    resolve(externalData);
                }
            });
        };

        const saveAndSendData = (externalData) => {
            
            trackingDataUtil.setExternalData(externalData);
            trackingDataUtil.saveExternalData();
            
            telemetry.sendCompleteInstallEvent();
            trackingDataUtil.setupUninstall(UNINSTALL_URL);
        };
    
        trackingDataUtil.setInstallDate().then(() => {
            
            trackingDataUtil.setInstallId().then(() => {
                
                checkParameterUrl().then(saveAndSendData);
            });
        });
    };

    const onUpdatedHandler = (lastVersion) => {
        const saveAndSendData = () => {
            telemetry.sendCompleteUpdateEvent(lastVersion);
        }
        saveAndSendData();
    };

    const onExtensionLaunchHandler = (ev) => {
        
        let promiseList = [];
        promiseList.push(new Promise((resolve, reject) => {
            storageUtil.load("externalData", trackingDataUtil.getExternalData(), (fetched) => {
                trackingDataUtil.setExternalData(fetched.externalData);
                
                resolve("externalData");
            });
        }));
    
        Promise.all(promiseList).then((resolutionMessage) => {
            
            if (ev.reason === "install") {
                
                onFirstInstallHandler();
            } else if (ev.reason === "update") {
                
                onUpdatedHandler(ev.lastVersion);
                setTimeout(() => {
                    chrome.runtime.reload();
                }, 6000);
            } else if (ev.reason === "startup") {
                onStartupHandler();
            } else {
                
            }
        });
    };

    const onFirstFetchReady = (fetched) => {
        onVersionReady(fetched.version);
        onAllReady();
    };
    
    telemetry.onExtensionLaunch(onExtensionLaunchHandler);
    
    storageUtil.load("version", "0.0.0.0", onFirstFetchReady);

    // check pref storage in firefox for another ACS instance
    var anotherAcsInstance = false;
    if (anotherAcsInstance === false) {
        adawareCloudService.init();
    } else {
        
    }
})();