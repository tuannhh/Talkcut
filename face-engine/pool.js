const os = require('os');
const path = require('path');
const { Worker } = require('worker_threads');
const face = require('./face');

const workerCount = Math.max(1, Number(process.env.FACE_ENGINE_WORKERS || Math.min(2, Math.max(1, os.cpus().length - 2))));
let workers, initializing, sequence = 0;
const queue = [];

function dispatch() {
  for (const worker of workers || []) {
    if (worker.busy || !queue.length) continue;
    const next = queue.shift(); worker.busy = next;
    worker.thread.postMessage({ id: next.id, buffer: next.buffer }, [next.buffer]);
  }
}
function createWorker() {
  const slot = { busy: null, retired: false, thread: new Worker(path.join(__dirname, 'worker.js')) };
  const replace = error => {
    if (slot.retired) return;
    slot.retired = true;
    if (slot.busy) { slot.busy.reject(error || new Error('Face-engine worker stopped unexpectedly')); slot.busy = null; }
    const index = workers.indexOf(slot);
    if (index >= 0) workers[index] = createWorker();
    dispatch();
  };
  slot.thread.on('message', result => {
    const task = slot.busy; slot.busy = null;
    if (!task) return;
    if (result.error) task.reject(new Error(result.error)); else task.resolve(result.faces);
    dispatch();
  });
  slot.thread.on('error', replace);
  slot.thread.on('exit', code => { if (code !== 0) replace(); });
  return slot;
}
async function initialize() {
  if (workers) return;
  if (!initializing) initializing = (async () => {
    await face.prefetchModels();
    workers = Array.from({ length: workerCount }, createWorker);
  })().catch(error => { initializing = null; throw error; });
  await initializing;
}
async function describe(buffer) {
  await initialize();
  const copy = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
  return new Promise((resolve, reject) => { queue.push({ id: ++sequence, buffer: copy, resolve, reject }); dispatch(); });
}
module.exports = { describe };
