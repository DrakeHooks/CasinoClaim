window.onunload = function () { };
var communicator = new MessageHostCommunicator();
communicator.on("InjectOwnJavascriptLibrary", (message, responseFunction) => {
    try {
        var script = document.createElement('script');
        script.id = "WAJavascriptLib";
        script.textContent = message.arg0;
        (document.head || document.documentElement).appendChild(script);
        script.remove();
        responseFunction({});
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
communicator.on("InjectOwnRuntimeJavascriptLibrary", (message, responseFunction) => {
    try {
        var scriptExists = runScript("typeof(wa)") != "undefined";
        if (!scriptExists) {
            var scriptTag = document.getElementById("WARuntimeJavascriptLib");
            if (scriptTag) {
                console.warn("Found script tag, but 'wa' was not defined. Fixing.");
                scriptTag.remove();
            }
            var script = document.createElement('script');
            script.id = "WARuntimeJavascriptLib";
            script.textContent = message.arg0;
            (document.head || document.documentElement).appendChild(script);
        }
        responseFunction({});
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
communicator.on("InjectJavascriptLibrary", (message, responseFunction) => {
    try {
        var scriptExists = runScript("typeof(PAD_JS_API_F424ACB1)") != "undefined";
        if (!scriptExists) {
            var scriptTag = document.getElementById("MS_PowerAutomate_JavascriptLib");
            if (scriptTag) {
                console.warn("Found script tag, but 'PAD_JS_API_F424ACB1' was not defined. Fixing.");
                scriptTag.remove();
            }
            var script = document.createElement('script');
            script.id = "MS_PowerAutomate_JavascriptLib";
            script.textContent = message.arg0;
            (document.head || document.documentElement).appendChild(script);
        }
        responseFunction({});
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
communicator.on("TravelThruHistory", (message, responseFunction) => {
    try {
        if (message.arg0)
            window.history.back();
        else
            window.history.forward();
        responseFunction({});
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
communicator.on("GetDimensions", (message, responseFunction) => {
    try {
        var totalWidth = document.scrollingElement.scrollWidth;
        var totalHeight = document.scrollingElement.scrollHeight;
        var screenWidth = document.documentElement.clientWidth;
        var screenHeight = document.documentElement.clientHeight;
        var viewHeight = window.innerHeight;
        var viewWidth = window.innerWidth;
        responseFunction({ totalWidth: totalWidth, totalHeight: totalHeight, screenWidth: screenWidth, screenHeight: screenHeight, viewHeight: viewHeight, viewWidth: viewWidth });
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
communicator.on("RunScript", (message, responseFunction) => {
    try {
        var result = runScript(message.arg0);
        responseFunction({ result: result });
    }
    catch (e) {
        responseFunction({ err: 'Error ' + e + ' ' + e.stack });
    }
});
function runScript(scriptAsString) {
    var targetWnd = window;
    var targetDoc = window.document;
    var script = targetDoc.createElement('script');
    targetWnd._result = undefined;
    targetWnd._complete = false;
    targetWnd._timeout = 100;
    script.textContent = 'var result = undefined; try{ result = ' + scriptAsString + ';}catch(e){}; document.documentElement.setAttribute("result", result); document.documentElement.setAttribute("complete", "true");';
    (targetDoc.head || targetDoc.documentElement).appendChild(script);
    script.parentNode.removeChild(script);
    var cb = function (wnd) {
        if (wnd.document.documentElement.getAttribute("complete") != "true" && wnd._timeout > 0) {
            wnd._timeout = wnd._timeout - 1;
            sleep(1);
            cb(wnd);
        }
        else {
            return wnd.document.documentElement.getAttribute("result") + '';
        }
    };
    var result = cb(targetWnd);
    return result;
}
function sleep(milliseconds) {
    var start = new Date().getTime();
    for (var i = 0; i < 1e7; i++) {
        if ((new Date().getTime() - start) > milliseconds) {
            break;
        }
    }
}
communicator.connectToBackgroundScript();
try {
    communicator.post({ notify: "init_tab" });
}
catch (e) {
    console.error("Post 'init_tab' message failed: " + e);
}
