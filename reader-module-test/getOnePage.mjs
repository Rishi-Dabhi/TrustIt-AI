import { WebSocket } from 'ws';

// Get URL from CLI args  
const url = process.argv[2];  

if (!url) {  
  console.error('Usage: node getOnePage.mjs <URL>');  
  process.exit(1);  
}  

const ws = new WebSocket('ws://localhost:8080');  

ws.on('open', () => {  
  console.log('Connected to server. Sending URL:', url);  
  ws.send(url);  
});  

ws.on('message', (data) => {  
  const response = JSON.parse(data);  
  if (response.error) {  
    console.error('Error:', response.error);  
  } else {  
    if (typeof response === 'string')
      console.log(response)
    else {
      console.log('\n--- HEADLINE ---\n', response.title);  
      console.log('\n--- CONTENT ---\n', response.content);  
    } 
} 
  ws.close();  
});  

ws.on('error', (err) => {  
  console.error('WebSocket error:', err.message);  
});  

ws.on('close', () => {  
  console.log('Disconnected.');  
});  
