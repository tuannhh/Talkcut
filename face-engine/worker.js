const { parentPort } = require('worker_threads');
const face = require('./face');

parentPort.on('message', async ({ id, buffer, type }) => {
  if (type === 'status') { parentPort.postMessage({ id, status: face.status() }); return; }
  try { parentPort.postMessage({ id, faces: await face.describe(Buffer.from(buffer)) }); }
  catch (error) { parentPort.postMessage({ id, error: error.message }); }
});
