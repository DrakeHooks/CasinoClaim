

document.addEventListener("DOMContentLoaded", function(event) {
    if ((window.location.hostname).includes('yahoo.com')) {
        if(window.location.pathname.includes("/search")) {
            var urls = {};
            var results;
            results = document.querySelectorAll("#web ol.searchCenterMiddle li div.compTitle h3.title");
            
            for(var i=0; i < results.length; i++) {
                if (results[i].children[0].href !== undefined) {
                    var url = results[i].children[0].href; 
                    // only to get url from yahoo redirect url
                    var mySubString = url.substring(
                        url.lastIndexOf("/RU=") + 4, 
                        url.lastIndexOf("/RK=")
                    );

                    var baseUrl = new URL(decodeURIComponent(mySubString));
                    var hostname = baseUrl.hostname;
                    var domain = hostname.replace("www.", "");
                    if (domain != null) {
                        urls[i] = domain;
                    }
                    
                }
            }

            

            chrome.runtime.sendMessage({
                message: "validateUrls",
                urls: urls
            }, function(response) {
                for (var key in response.urls.validUrls) {
                    var icon = document.createElement('img');
                    icon.setAttribute("src", 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACK0lEQVQ4jXWSTWgTURSFv6RpmhTTULU1GBRpUxCLuhDGhQq2LqwZBBW60IAgKuhCwYUYEAWVgIKbFF2pmyJuKuLCjNKFothSBrFotFI1WuoftcbYP9v8TeRNZ8Y0jnfz3rv3nHPvO+85sAkpEZaAQ0CnUe0BrquyolaiLQEpEV4MRIDDwFo7YeAVcA24qcrKT11ASoRbgajRraYc7Xf79HUiN1UplAXuADEX8AhoMCtuZzX7mzvZtaKDBs8SPTc+l+bupwd0p3rIaXmMRnuBdjFBySR7qmroki6wvr7Vdv4XmdccV88wV8xaOScwax4Ohvb9lzw8kaJUmseURUYIDM+76WD3yg5b8vN0kuhgTJ9QYBx/vR8VAqppmK96Ed2p26SzGYv89LtKLBnn8oazrPaHdIxpLtAvBBSxmyn8plgq6sYdGTjFt9kxer8+puvNDeLSeZp9q3SGwAisEb0uQ2AsrxWW9Y8/Y0ewjVqXhwN9J/C767iyMUajZ6k1kcDktYLY/gDuV3259U4LRlqKwPa3kynCwW201DURrA0QadpDwNtokUXn04MX+ZWbFMdzqqw8cRq1q0ByZPozRweifJwepS2wieXegEUWOVETGGAIiFPxlcX37QN8ToeDdfVrCBn3fj81wsvMEJp4RxDtN6uyklwgYIi0A/cAr+17gnBvpyorD82EeQU9jMJWMbEN+QOwpZz8zwRlk4iHPgkcAzTDo0uqrMwsAAJ/AOvfvmoIgqFPAAAAAElFTkSuQmCC');
                    icon.setAttribute('style', 'margin-left:10px');
                    
                    results[key].children[0].append(icon);
                }
                for (var key in response.urls.unvalidUrls) {
                    var icon = document.createElement('img');
                    icon.setAttribute("src", 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACDUlEQVQ4jW2SzWsTURTFf5kkbUrbJA6o/0DEhQxEUVcGxIU73Yi6UDdVqQs3LhRxKwpFuhBxUWwF0Y0RsxK/KqLUblSsMroQQ7NOkTFNGk1mMnly36TTJM2FYe7Hueed+96NMMAcK7MfOAcc71SfALOmXfzYjw4JHCuzBTgNnAesQcTAd+Ae8Mi0i44mcKzMLuBq57ThHvZ0Wv9VpdJP1AQKwA0hWAG2hqWhIRJnJxk+dhJj23adaq+UaT59TGNuBly3m6gsBCo8MTHC2Mx9Yrv3DtTfWvrM2uQEqvEvzBlAGCUuXNTNjQdzNAv5Db2FvM5JTTBd5oiCJSBLJEJ64RORZAraPvVrl4nnDmqot/CO0Zu3wIiiqqtUcvtAaeHfYoA8TTaSSgfNWleU0etTVM+c0GHyYV7n9JjJFIJVlT8SLsoIz/VN19fA90Nx7usX+hLlEz803w+wgc2vE5TxPLwP74PmN69w518yNn1Hf+JLTo8jGM8T9zcQMDtW5pK8xurRw6pdq6lWaVkp11Whua7OSU0wgnWszJX1VxC7C9h+aZnaxKlglHh8Q7b4vq9rggF+ALfpW2VZ30VgHMMglt1DdMdOXfN//aT19Qu02xJWgQOmXbR7CDokh4BnwMjATYK/wBHTLr7tXqTQOgV5/NKAZtGe627epKBLyTgglyRrJ7rljqZMu1jvAQL/ATlR3jEN4BMsAAAAAElFTkSuQmCC');
                    icon.setAttribute('style', 'margin-left:10px');
                    
                    results[key].children[0].append(icon);
                }
            });
        }
    }
});