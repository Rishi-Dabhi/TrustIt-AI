#### install

The extension is currently working only on Chrome (>=116)
To run the extension, you need to enable 'Developer mode' in top right of [chrome://extensions/](chrome://extensions/)

'Load unpacked' and select the extension *folder*.

In the extension's card, click 'service worker' to view console output from the extension.

If 'Errors' button appears and [they](chrome://extensions/?errors=hinaaekfclfooomagbimbajnckjohcak) show `socket = new WebSocket(WS_URL);`, there is no websocket server running for the extension to connect to.

If this is unexpected, verify `WS_URL` in `extension/background/background.js` is pointing to the local or remote server you are expecting (and if it is remote, that it is permitted in `manifest.json`).

You can run the local websocket server locally by following the instructions in [its README](../reader-module-test/README.md).

