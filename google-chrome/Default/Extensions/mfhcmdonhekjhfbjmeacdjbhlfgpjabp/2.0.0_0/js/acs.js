'use strict';

const adawareCloudService = (function () {
    const ONE_SECOND = 1000;
    const ONE_MINUTE = 60 * ONE_SECOND;
    const ONE_HOUR = 60 * ONE_MINUTE;
    const ONE_DAY = 24 * ONE_HOUR;

    const ACS_WHITELIST_URL = "https://acs.lavasoft.com/api/v2.0/url/whitelist";
    const ACS_BLACKLIST_URL = "https://acs.lavasoft.com/api/v2.0/url/blacklist";
    const ACS_PERMANENT_WHITELIST_URL = "https://acs.lavasoft.com/api/v2.0/url/permanentWhitelist";

    const UPDATE_ASSETS_FREQUENCY = ONE_DAY;

    const asyncSendTelemetryData = function (eventType, telemetryData) {
        setTimeout(function () {
            telemetry.sendMetaEvent(eventType, telemetryData);
        }, 5 * ONE_SECOND); // set to 5 seconds to give a chance for all other tracking data to initialize when fetching from extension storage (eg. install date, install source, etc.)
    };

    const httpGetAsync = async (url, onLoad, onError) => {
        try {
            const response = await fetch(url)
            const data = await response.json();
            return onLoad.call(this, data, response.status);
        } catch (error) {
            return onError.call(this, error, error.status);
        }
    };

    const getRemoteAsset = (assetUrl, callback, failHandler) => {
        var downloadStart = Date.now();
        

        var failHandlerWrapper = function (httpStatus) { // retry to download lists until we get non empty lists
            
            setTimeout(function () {
                getRemoteAsset(assetUrl, callback, failHandler);
            }, ONE_HOUR);

            failHandler(httpStatus);
        };

        var listReceivedHandler = function (rawAssetList, httpStatus) {
            
            var parsedList = [];
            var entryNumber = 0;
            parsedList = rawAssetList;
            entryNumber = parsedList.length;

            var duration = Date.now() - downloadStart;
            

            if (parsedList.length === 0) {
                
                failHandlerWrapper(httpStatus);
            } else {
                callback(parsedList, httpStatus);
            }
        };

        httpGetAsync(assetUrl, listReceivedHandler, failHandlerWrapper);
    };

    const ACS = function () {
        this.whitelistDomains = null;
        this.blacklistDomains = null;
        this.permanentWhitelistDomains = null;
    };

    /**
     * @function init
     * @description Download/Load from storage ACS assets (whitelist and blacklist)
     */
    ACS.prototype.init = function () {
        
        let acsWhitelist = null;
        let acsBlacklist = null;
        let acsPermanentWhitelist = null;
        let acsWhitelistLastDownloadTime = null;
        let acsBlacklistLastDownloadTime = null;
        let acsPermanentWhitelistLastDownloadTime = null;

        const loadDataFromStoragePromise = Promise.all(
            [
                new Promise((resolve, reject) => {
                    storageUtil.load('acsWhitelist', null, (fetched) => {
                        acsWhitelist = fetched.acsWhitelist;
                        resolve("acsWhitelist");
                    });
                }),
                new Promise(function (resolve, reject) {
                    storageUtil.load('acsBlacklist', null, function (fetched) {
                        acsBlacklist = fetched.acsBlacklist;
                        resolve("acsBlacklist");
                    });
                }),
                new Promise(function (resolve, reject) {
                    storageUtil.load('acsPermanentWhitelist', null, function (fetched) {
                        acsPermanentWhitelist = fetched.acsPermanentWhitelist;
                        resolve("acsPermanentWhitelist");
                    });
                }),
                new Promise(function (resolve, reject) {
                    storageUtil.load("acsWhitelistLastDownloadTime", 0, function (fetched) {
                        if (fetched.acsWhitelistLastDownloadTime === null || fetched.acsWhitelistLastDownloadTime === undefined) {
                            acsWhitelistLastDownloadTime = 0;
                        } else {
                            acsWhitelistLastDownloadTime = fetched.acsWhitelistLastDownloadTime;
                        }
                        resolve("acsWhitelistLastDownloadTime");
                    });
                }),
                new Promise(function (resolve, reject) {
                    storageUtil.load("acsBlacklistLastDownloadTime", 0, function (fetched) {
                        if (fetched.acsBlacklistLastDownloadTime === null || fetched.acsBlacklistLastDownloadTime === undefined) {
                            acsBlacklistLastDownloadTime = 0;
                        } else {
                            acsBlacklistLastDownloadTime = fetched.acsBlacklistLastDownloadTime;
                        }
                        resolve("acsBlacklistLastDownloadTime");
                    });
                }),
                new Promise(function (resolve, reject) {
                    storageUtil.load("acsPermanentWhitelistLastDownloadTime", 0, function (fetched) {
                        if (fetched.acsPermanentWhitelistLastDownloadTime === null || fetched.acsPermanentWhitelistLastDownloadTime === undefined) {
                            acsPermanentWhitelistLastDownloadTime = 0;
                        } else {
                            acsPermanentWhitelistLastDownloadTime = fetched.acsPermanentWhitelistLastDownloadTime;
                        }
                        resolve("acsPermanentWhitelistLastDownloadTime");
                    });
                }),
            ]
        );

        loadDataFromStoragePromise.then((resolutionMessage) => {
            

            var acsWhitelistTimeElapsedSinceLastDownload = Date.now() - acsWhitelistLastDownloadTime;
            var acsBlackListTimeElapsedSinceLastDownload = Date.now() - acsBlacklistLastDownloadTime;
            var acsPermanentWhitelistTimeElapsedSinceLastDownload = Date.now() - acsPermanentWhitelistLastDownloadTime;

            // handle very first download
            if (acsWhitelistLastDownloadTime === 0) {
                acsWhitelistTimeElapsedSinceLastDownload = 0;
            }
            if (acsBlacklistLastDownloadTime === 0) {
                acsBlackListTimeElapsedSinceLastDownload = 0;
            }
            if (acsPermanentWhitelistLastDownloadTime === 0) {
                acsPermanentWhitelistTimeElapsedSinceLastDownload = 0;
            }

            const onACSWhitelistDownloaded = (whitelist, httpStatus) => {
                var hashedWhitelist = whitelist;
                ACS.whitelistDomains = hashedWhitelist;
                
                storageUtil.save("acsWhitelist", hashedWhitelist);
                storageUtil.save("acsWhitelistLastDownloadTime", Date.now());

                var eventData = {
                    List: "Whitelist",
                    LastUpdate: acsWhitelistTimeElapsedSinceLastDownload / 1000, // in seconds
                    HttpStatus: httpStatus
                };
                asyncSendTelemetryData("AcsListDownload", eventData);
            };

            const onACSWhitelistDownloadFailed = (httpStatus) => {
                var eventData = {
                    List: "Whitelist",
                    LastUpdate: acsWhitelistTimeElapsedSinceLastDownload / 1000, // in seconds
                    HttpStatus: httpStatus
                };
                asyncSendTelemetryData("AcsListDownload", eventData);
            };

            const onACSBlacklistDownloaded = (blacklist, httpStatus) => {
                var hashedBlacklist = blacklist;
                ACS.blacklistDomains = hashedBlacklist;
                
                storageUtil.save("acsBlacklist", hashedBlacklist);
                storageUtil.save("acsBlacklistLastDownloadTime", Date.now());

                var eventData = {
                    List: "Blacklist",
                    LastUpdate: acsBlackListTimeElapsedSinceLastDownload / 1000, // in seconds
                    HttpStatus: httpStatus
                };
                asyncSendTelemetryData("AcsListDownload", eventData);
            };

            const onACSBlacklistDownloadFailed = (httpStatus) => {
                var eventData = {
                    List: "Blacklist",
                    LastUpdate: acsBlackListTimeElapsedSinceLastDownload / 1000, // in seconds
                    HttpStatus: httpStatus
                };
                asyncSendTelemetryData("AcsListDownload", eventData);
            };

            const onACSPermanentWhitelistDownloaded = (whitelist, httpStatus) => {
                var hashedWhitelist = whitelist;
                ACS.permanentWhitelistDomains = hashedWhitelist;
                
                storageUtil.save("acsPermanentWhitelist", hashedWhitelist);
                storageUtil.save("acsPermanentWhitelistLastDownloadTime", Date.now());

                var eventData = {
                    List: "PermanentWhitelist",
                    LastUpdate: acsPermanentWhitelistTimeElapsedSinceLastDownload / 1000, // in seconds
                    HttpStatus: httpStatus
                };
                asyncSendTelemetryData("AcsListDownload", eventData);
            };

            const onACSPermanentWhitelistDownloadFailed = (httpStatus) => {
                var eventData = {
                    List: "PermanentWhitelist",
                    LastUpdate: acsPermanentWhitelistTimeElapsedSinceLastDownload / 1000, // in seconds
                    HttpStatus: httpStatus
                };
                asyncSendTelemetryData("AcsListDownload", eventData);
            };

            if (acsWhitelist === null || acsWhitelistTimeElapsedSinceLastDownload > UPDATE_ASSETS_FREQUENCY) {
                getRemoteAsset(ACS_WHITELIST_URL, onACSWhitelistDownloaded, onACSWhitelistDownloadFailed);
            } else {
                ACS.whitelistDomains = acsWhitelist;
                
            }

            if (acsBlacklist === null || acsBlackListTimeElapsedSinceLastDownload > UPDATE_ASSETS_FREQUENCY) {
                getRemoteAsset(ACS_BLACKLIST_URL, onACSBlacklistDownloaded, onACSBlacklistDownloadFailed);
            } else {
                ACS.blacklistDomains = acsBlacklist;
                
            }

            if (acsPermanentWhitelist === null || acsPermanentWhitelistTimeElapsedSinceLastDownload > UPDATE_ASSETS_FREQUENCY) {
                getRemoteAsset(ACS_PERMANENT_WHITELIST_URL, onACSPermanentWhitelistDownloaded, onACSPermanentWhitelistDownloadFailed);
            } else {
                ACS.permanentWhitelistDomains = acsPermanentWhitelist;
                
            }

            const updateACSAssetsTimer = setInterval(function () {
                
                getRemoteAsset(ACS_WHITELIST_URL, onACSWhitelistDownloaded, onACSWhitelistDownloadFailed);
                getRemoteAsset(ACS_BLACKLIST_URL, onACSBlacklistDownloaded, onACSBlacklistDownloadFailed);
                getRemoteAsset(ACS_PERMANENT_WHITELIST_URL, onACSPermanentWhitelistDownloaded, onACSPermanentWhitelistDownloadFailed);
            }, UPDATE_ASSETS_FREQUENCY);
        });
    };

    /**
     * @function filteredUrlsRequest
     * @description Filter Urls request
     * @param {Object} urls - urls containing relevant information about domains
     * @return {Object} validUrls and unvalidUrls - Filtering result
     */
    ACS.prototype.filterUrlRequest = function (urls) {
        var response = { validUrls: {}, unvalidUrls: {} } 
        for (var key in urls) {
            if (ACS.blacklistDomains.includes(urls[key])) {
                response.unvalidUrls[key] = urls[key];
            } else {
                response.validUrls[key] = urls[key];
            }
        }
        return response;
    };

    return new ACS();
})();