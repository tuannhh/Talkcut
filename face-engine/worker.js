const { parentPort } = require('worker_threads');
const face = require('./face');

parentPort.on('message', async ({ id, buffer }) => {
  try { parentPort.postMessage({ id, faces: await face.describe(Buffer.from(buffer)) }); }
  catch (error) { parentPort.postMessage({ id, error: error.message }); }
});
