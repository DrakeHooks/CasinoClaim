(function () {
    'use strict';

    var details = {};

    var trackingData = {};

    (function () {
        var matches = /details=([^&]+)/.exec(window.location.search);
        var baseUrl = new URL(matches[1]);

        
        if (matches === null) {
            return;
        }
        details = { url: matches[1], hn: baseUrl.hostname };
        
    })();

    var getTargetHostname = function () {
        var hostname = details.hn;
        var elem = document.querySelector('#proceed select');
        if (elem !== null) {
            hostname = elem.value;
        }
        return hostname;
    };

    var proceedToURL = function () {
        window.location.replace(details.url);
    };

    var continueToSite = function () {
        if (uDom.nodeFromId('proceedPermanent').checked) {
            proceedPermanent();
        } else {
            proceedTemporary();
        }

        trackingData.action = "cont";
        // track 'continue to site' button
        chrome.runtime.sendMessage({
            message:  'adaware-telemetry',
            what: 'WarningPageButtons',
            data: trackingData,
            url: details.url
        });
    };

    var proceedTemporary = function () {
        chrome.runtime.sendMessage({
            message: "documentBlocked",
            what: "temporarilyWhitelistDocument",
            hostname: getTargetHostname()
        }, proceedToURL);
    };

    var proceedPermanent = function () {
        chrome.runtime.sendMessage({
            message: "documentBlocked",
            what: "permanentWhitelistDocument",
            hostname: getTargetHostname()
        }, proceedToURL);
    };

    var goBack = function () {
        if (window.history.length <= 1) {
            window.location.assign("about:blank");
        } else {
            window.history.go(-2);
        }

        trackingData.action = "back";
        // track 'back' button 
        chrome.runtime.sendMessage({
            message:  'adaware-telemetry',
            what: 'WarningPageButtons',
            data: trackingData
        });
    };

    uDom.nodeFromSelector('#theURL').textContent = details.url;

    uDom('#back').on('click', goBack);
    uDom('#continueToSite').attr('href', details.url || "").on('click', continueToSite);
})();