import { WebSocketServer } from 'ws';
import { extractArticle } from './getPage.mjs';

export function createWSServer(port = 8080) {
    const wss = new WebSocketServer({ port });

    wss.on('connection', (ws) => {
        ws.on('message', async (message) => {            
            try {
                console.log('GOT:', {message});
                
                const url = message.toString();
                const article = await extractArticle(url);
                ws.send(JSON.stringify(article));
            } catch (error) {
                ws.send(JSON.stringify({ error: error.message }));
            }
        });
    });

    return wss;
}
