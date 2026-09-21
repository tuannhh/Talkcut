const http = require('http');
const pool = require('./pool');
const port = Number(process.env.PORT || 3210);

function json(response, status, payload) { response.writeHead(status, { 'content-type': 'application/json' }); response.end(JSON.stringify(payload)); }
http.createServer(async (request, response) => {
  if (request.method === 'GET' && request.url === '/health') return json(response, 200, { status: 'ok' });
  if (request.method === 'GET' && request.url === '/status') {
    try { return json(response, 200, await pool.status()); }
    catch (error) { return json(response, 503, { error: error.message }); }
  }
  if (request.method !== 'POST' || request.url !== '/v1/describe') return json(response, 404, { error: 'not found' });
  const chunks = []; let size = 0;
  request.on('data', chunk => { size += chunk.length; if (size > 24 * 1024 * 1024) request.destroy(); else chunks.push(chunk); });
  request.on('end', async () => {
    try { json(response, 200, { faces: await pool.describe(Buffer.concat(chunks)) }); }
    catch (error) { json(response, 503, { error: error.message }); }
  });
}).listen(port, '0.0.0.0', () => console.log(`TalkCut face engine listening on ${port}`));
