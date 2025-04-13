import { createWSServer } from './ws-server.mjs';
import { closeBrowser } from './getPage.mjs';

let port = Number(process.argv[2]) || 8080;

const wss = createWSServer(port);

process.on('SIGINT', async () => {
    await closeBrowser();
    wss.close();
    process.exit();
});

console.log('Websocket server running on ws://localhost:8080');