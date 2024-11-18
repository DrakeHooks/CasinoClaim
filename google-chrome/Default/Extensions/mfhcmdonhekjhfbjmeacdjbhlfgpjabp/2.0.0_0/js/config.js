const config = (function () {
    configurationData = {
        "productId": "ws",
        "flowUrl": "https://flow.lavasoft.com/v1/event-stat?", // Event flow url
        "isStaticExternalData": true, //if this is true than externalData(object below) is mandatory
        "externalData": {
            "PartnerID": "",
            "CampaignID": "",
            "sourceTraffic": "",
            "OfferID": "",
            "CLID": "",
            "MK": "",
            "IK": "",
            "extensionID": chrome.runtime.id
        }
    };
    return {
        configurationData: configurationData
    }
})();