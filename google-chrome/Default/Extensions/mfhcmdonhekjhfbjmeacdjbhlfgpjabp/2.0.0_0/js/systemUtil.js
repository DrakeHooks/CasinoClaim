const systemUtil = (function () {
    /* Get Data from Manifest */
    let manifest = chrome.runtime.getManifest();
    /* Variable for browser details */
    let browserEnvironment = null;
    let getUILanguage = chrome.i18n.getUILanguage();

    /* Get Browser Environment Data*/
    const browserEnvironmentData = function () {
        var browserInfo = getBrowserInfo();
        this.BrowserFamily = browserInfo.name;
        this.BrowserVersion = browserInfo.version;
        this.BrowserLocale = browserInfo.lang;
        this.Platform = getOSName();
        this.ExtensionVersion = manifest.version;
        this.ExtensionLocale = getUILanguage;
    };

    /*  Get Browser Info*/
    const getBrowserInfo = () => {
        var browserNameAndVersion = getBrowserNameAndVersion().split(" ");
        return {
            name: browserNameAndVersion[0],
            version: browserNameAndVersion[1],
            lang: navigator.language || navigator.userLanguage
        };
    }

    /*  Get Browser Name and Version*/
    const getBrowserNameAndVersion = () => {
        var ua = navigator.userAgent,
            tem,
            M = ua.match(/(vivaldi|opera|chrome|safari|firefox|msie|trident(?=\/))\/?\s*([0-9|\.]+)/i) || [];
        if (/trident/i.test(M[1])) {
            tem = /\brv[ :]+([0-9|\.]+)/g.exec(ua) || [];
            return 'IE ' + (tem[1] || '');
        }
        if (M[1] === 'Firefox') {
            tem = ua.match(/\b(PaleMoon)\/([0-9|\.]+)/);
            if (tem != null) return tem.slice(1).join(' ');
        }
        if (M[1] === 'Chrome') {
            tem = ua.match(/\b(OPR|Edge|Edg)\/([0-9|\.]+)/);
            if (tem != null) return tem.slice(1).join(' ').replace('OPR', 'Opera').replace('Edg', 'Edge');
        }
        M = M[2] ? [M[1], M[2]] : [navigator.appName, navigator.appVersion, '-?'];
        if ((tem = ua.match(/version\/([0-9|\.]+)/i)) != null) M.splice(1, 1, tem[1]);
        return M.join(' ');
    }

    /*  Get Operating system Info*/
    const getOSName = () => {
        var OSName = "other";
        if (navigator.appVersion.indexOf("Win") != -1) OSName = "windows";
        else if (navigator.appVersion.indexOf("Mac") != -1) OSName = "mac";
        else if (navigator.appVersion.indexOf("Linux") != -1) OSName = "linux";
        return OSName;
    }

    return {
        browserEnvironmentData: browserEnvironmentData,
        getBrowserInfo: getBrowserInfo,
        getBrowserNameAndVersion: getBrowserNameAndVersion,
        getOSName: getOSName
    }
})();