const os = require('os');
const path = require('path');
const { Worker } = require('worker_threads');
const face = require('./face');
const gpu = require('./gpu');

const ACCEL = (process.env.FACE_ENGINE_ACCEL || 'auto').toLowerCase();
const detectedGPU = ACCEL !== 'cpu' ? gpu.detectGPU() : null;
const cpuDefaultWorkers = Math.min(2, Math.max(1, os.cpus().length - 2));
const gpuTierWorkers = detectedGPU ? gpu.workersForVram(detectedGPU.vramMb) : null;
const workerCount = Math.max(1, Number(process.env.FACE_ENGINE_WORKERS || gpuTierWorkers || cpuDefaultWorkers));
if (detectedGPU) {
  // Split detected VRAM evenly across workers (each holds its own CUDA context), leaving headroom for the driver.
  if (!process.env.FACE_ENGINE_GPU_MEM_LIMIT_MB) process.env.FACE_ENGINE_GPU_MEM_LIMIT_MB = String(Math.floor((detectedGPU.vramMb * 0.85 * 1024 * 1024) / workerCount / 1024 / 1024));
  console.log(`Face engine: GPU ${detectedGPU.name} (${detectedGPU.vramMb} MB VRAM) detected, ${workerCount} worker(s), ~${process.env.FACE_ENGINE_GPU_MEM_LIMIT_MB} MB VRAM/worker`);
} else if (ACCEL !== 'cpu') {
  console.log(`Face engine: no NVIDIA GPU detected, running CPU-only with ${workerCount} worker(s)`);
}
let workers, initializing, sequence = 0;
const queue = [];

function dispatch() {
  for (const worker of workers || []) {
    if (worker.busy || !queue.length) continue;
    const next = queue.shift(); worker.busy = next;
    if (next.type === 'status') worker.thread.postMessage({ id: next.id, type: 'status' });
    else worker.thread.postMessage({ id: next.id, buffer: next.buffer }, [next.buffer]);
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
    if (result.error) task.reject(new Error(result.error));
    else task.resolve(result.status !== undefined ? result.status : result.faces);
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
async function status() {
  if (!workers) {
    // Report detection/tiering without forcing a model download+load just to answer a status check.
    return { accelMode: ACCEL, gpu: detectedGPU, activeProvider: null, modelsLoaded: false, workerCount };
  }
  const worker = await new Promise((resolve, reject) => { queue.push({ id: ++sequence, type: 'status', resolve, reject }); dispatch(); });
  return { ...worker, workerCount };
}
module.exports = { describe, status };
