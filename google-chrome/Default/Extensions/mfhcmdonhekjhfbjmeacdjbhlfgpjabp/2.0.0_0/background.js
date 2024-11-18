try {
    importScripts('/js/config.js', '/js/storageUtil.js', '/js/systemUtil.js', '/js/trackingDataUtil.js', '/js/telemetry.js', '/js/acs.js', '/js/start.js', '/js/backgroundScript.js');
} catch (e) {
    console.error(e);
}