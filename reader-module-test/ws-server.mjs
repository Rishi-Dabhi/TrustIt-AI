import { WebSocketServer } from 'ws';
import { extractArticle } from './getPage.mjs';

const SERVERSIDE_HEARTBEAT= Infinity;

export function createWSServer(port = 8080) {
    const wss = new WebSocketServer({ port });

    wss.on('connection', (ws) => {
        ws.on('message', async (message) => {          
            const messageJson = JSON.parse(message.toString());
            if (messageJson.ping) {
                ws.send(JSON.stringify({ data: {pong: true} }));
            }

            try {
                const { url, tabId, type, origin } = messageJson;

                // console.log('GOT:', { url, tabId, type, origin });
                console.log('GOT:', url);
                
                const sent = await extractArticle(url)
                    .then(response => {
                        if (!response.ignored) {
                            ws.send(JSON.stringify({ data: response }));
                            return true;
                        }
                    });                
            } catch (error) {
                ws.send(JSON.stringify({ error: error.message }));
            }
        });
    });

    return wss;
}
