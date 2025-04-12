const CLIENTSIDE_HEARTBEAT = 25000;

// Shared WebSocket manager (cross-browser)
let socket = null;

let WS_URL='ws://localhost:8080';
// const WS_URL = 'wss://ws.veracity-engine.rocks';

function connectWebSocket() {
  socket = new WebSocket(WS_URL);

  socket.onopen = () => console.log('WebSocket connected');
  socket.onclose = () => setTimeout(connectWebSocket, 5000); // Reconnect
  socket.onerror = (err) => console.error('WebSocket error:', err);


  socket.onmessage = event=> {
    console.log({event});
    // data = JSON.parse(event.data);
    // console.log({data});
  };
    
}

// Initialize (Chrome service worker or Firefox background page)
console.log('Veracity Engine - extension starting ', new Date());

function flingUrl( { url, tabId, type, origin=null }) {
  let payload;    
  switch (type) {
    case "nav" : {
        payload = { url };
    };
    case "new" : {
        payload = { url };
    };
  }

  if (socket && socket?.readyState === WebSocket.OPEN) 
    socket.send(JSON.stringify(payload))
  else
    console.warn('WebSocket not ready');
}


// Track tab URL changes
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  flingUrl( { 
    url: (changeInfo && changeInfo.url) || tab.pendingUrl || tab.url , 
    type:'nav', 
    tabId: tab.id 
  } )
});
// Track new tab creation
chrome.tabs.onCreated.addListener((tab) => {
  flingUrl( { 
    url: tab.pendingUrl || tab.url, 
    type:'nav', 
    tabId: tab.id 
  } )
});
console.log('onUpdated, onCreated listeners added.', new Date());

connectWebSocket();

// Heartbeat for Chrome MV3
setInterval(() => {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send('ping');
  }
}, CLIENTSIDE_HEARTBEAT);



// Robust event listeners
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = changeInfo.url || tab.pendingUrl || tab.url;
  if (!url) return;

  flingUrl({
    url,
    tabId,
    type: 'navigation'
  });
});

chrome.tabs.onCreated.addListener((tab) => {
  const url = tab.pendingUrl || tab.url;
  if (!url) return;

  flingUrl({
    url,
    tabId: tab.id,
    type: 'new_tab'
  });
});
