const telemetry = (function () {
    /* Import Configuration data from config file */
    let configurationData = config.configurationData;
    /* Flow Url */
    let flowUrl = configurationData.flowUrl;
    /* Event Prameters */
    let eventParameters = {
        ProductID: configurationData.productId, // static via config file
        Type: "" //dynamica for each request
    };
    /* after install necessary installdata */
    const init = () => {
        onFirstRun();
    }
    /* Send Complete install event  */
    const sendCompleteInstallEvent = () => {
        setTimeout(function () {
            trackingDataUtil.getInstallDate().then((date) => {
                trackingDataUtil.getInstallId().then((id) => {
                    storageUtil.load('externalData', '', function (ext) {
                        let installDate = new Date(date.installDate).toISOString();
                        installDate = {installDate: installDate}
                        let installId = id;
                        let externalData = ext.externalData;
                        let browserEnvironment = new systemUtil.browserEnvironmentData();
                        let completeInstallEventData = trackingDataUtil.trackingData(browserEnvironment, installDate, installId, externalData);
                        sendEvent("CompleteInstall", completeInstallEventData);
                    });
                });
            });
        }, 2000);
    }
    /* Send Daily Activity event */
    const sendDailyActivityEvent = (dailyActivityData) => {
        setTimeout(function () {
            trackingDataUtil.getInstallDate().then((date) => {
                trackingDataUtil.getInstallId().then((id) => {
                    storageUtil.load('externalData', '', function (ext) {
                        let dailyData = dailyActivityData;
                        let installDate = new Date(date.installDate).toISOString();
                        installDate = {installDate: installDate}
                        let installId = id;
                        let externalData = ext.externalData;
                        let browserEnvironment = new systemUtil.browserEnvironmentData();
                        // 
                        let dailyActivityDataEvent = trackingDataUtil.trackingData(browserEnvironment, installDate, installId, externalData, dailyData);
                        sendEvent("DailyActivity", dailyActivityDataEvent);
                    });
                });
            });
        }, 2000);
    }

    /* Send Complete Update event */
    const sendCompleteUpdateEvent = (lastVersion) => {
        setTimeout(function () {
            trackingDataUtil.getInstallDate().then((date) => {
                trackingDataUtil.getInstallId().then((id) => {
                    storageUtil.load('externalData', '', function (ext) {
                        let installDate = new Date(date.installDate).toISOString();
                        installDate = {installDate: installDate}
                        let installId = id;
                        let externalData = ext.externalData;
                        let browserEnvironment = new systemUtil.browserEnvironmentData();
                        let fromExtensionVersion = {FromExtensionVersion: lastVersion};
                        let completeUpdateDataEvent = trackingDataUtil.trackingData(browserEnvironment, installDate, installId, externalData, fromExtensionVersion);
                        // 
                        sendEvent("CompleteUpdate", completeUpdateDataEvent);
                    });
                });
            });
        }, 2000);
    }

    /* send generic event by passing event type and data */
    const sendEvent = (eventType, data) => {
        
        eventParameters.Type = eventType;
        var flowUrlDestination = flowUrl + trackingDataUtil.dictToStringParams(eventParameters);

        fetch(flowUrlDestination, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            
        })
        .catch((error) => {
            // 
            try {
                let parsedResponse = JSON.parse(error);
                
            } catch (e) {
                
            }
        });
    }

    /* send event type, data with meta */
    const sendMetaEvent = (eventType, data) => {
        trackingDataUtil.getInstallDate().then((date) => {
            trackingDataUtil.getInstallId().then((id) => {
                storageUtil.load('externalData', '', function (ext) {
                    let installDate = new Date(date.installDate).toISOString();
                    installDate = {installDate: installDate}
                    let installId = id;
                    let externalData = ext.externalData;
                    let browserEnvironment = new systemUtil.browserEnvironmentData();
                    let datas = trackingDataUtil.trackingData(browserEnvironment, installDate, installId, externalData, data);
                    sendEvent(eventType, datas);
                });
            });
        });
    }

    /* first run  */
    const onFirstRun = () => {
        chrome.storage.local.get({
            'firstRun': true
        }, function (fetched) {
            if (fetched.firstRun === true) {
                chrome.storage.local.set({
                    'firstRun': false
                });
                trackingDataUtil.setInstallId().then((installId) => {
                    trackingDataUtil.setInstallDate(installId).then((installData) => {
                        if (installData == true) {
                            trackingDataUtil.saveExternalData();
                        }
                    });
                });
            }
        });
    }

    /* extension handler on launch */
    const onExtensionLaunch = (callback) => {
        const defaultVersion = "0.0.0.0";
        storageUtil.load("version", defaultVersion, (fetched) => {
            var lastVersion = fetched.version;
            var currentVersion = chrome.runtime.getManifest().version;

            if (currentVersion > lastVersion && lastVersion !== defaultVersion) {
                
                callback({ reason: "update", lastVersion: lastVersion });
            } else {
                storageUtil.load("firstRun", true, (fetched) => {
                    if (fetched.firstRun === true) {
                        callback({reason: "install"});
                        storageUtil.save("firstRun", false);
                    } else {
                        callback({reason: "startup"});
                    }
                });
            }
        });
    }

    return {
        init: init,
        sendCompleteInstallEvent: sendCompleteInstallEvent,
        sendDailyActivityEvent: sendDailyActivityEvent,
        sendCompleteUpdateEvent: sendCompleteUpdateEvent,
        sendEvent: sendEvent,
        sendMetaEvent: sendMetaEvent,
        onExtensionLaunch: onExtensionLaunch
    }
})();