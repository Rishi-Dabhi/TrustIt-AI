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
}

// Initialize (Chrome service worker or Firefox background page)
console.log('Veracity Engine - extension starting ', new Date());

connectWebSocket();

// Heartbeat for Chrome MV3 (25s interval)
setInterval(() => {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send('ping');
  }
}, CLIENTSIDE_HEARTBEAT);
