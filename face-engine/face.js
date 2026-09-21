/*
 * Local face engine for TalkCut.
 *
 * It uses SCRFD (detector + five landmarks) and ArcFace r50 (appearance
 * descriptor).  The five-point alignment is important for matching the same
 * speaker across wide, close and partially turned camera shots.  Descriptors
 * are kept in process only and are scoped to the active TalkCut source.
 */
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const ort = require('onnxruntime-node');
const gpu = require('./gpu');

const MODEL_DIR = process.env.FACE_MODEL_DIR || '/data/face-models';
const MODELS = {
  scrfd: {
    file: 'scrfd_10g.onnx',
    url: 'https://huggingface.co/immich-app/buffalo_l/resolve/main/detection/model.onnx?download=true',
    minimum: 10_000_000,
  },
  arcface: {
    file: 'arcface_w600k_r50.onnx',
    url: 'https://huggingface.co/immich-app/buffalo_l/resolve/main/recognition/model.onnx?download=true',
    minimum: 100_000_000,
  },
};

async function model(kind) {
  const spec = MODELS[kind];
  fs.mkdirSync(MODEL_DIR, { recursive: true });
  const target = path.join(MODEL_DIR, spec.file);
  if (fs.existsSync(target) && fs.statSync(target).size >= spec.minimum) return target;
  const temporary = target + '.part';
  const response = await fetch(spec.url);
  if (!response.ok) throw new Error(`Cannot download ${spec.file}: HTTP ${response.status}`);
  fs.writeFileSync(temporary, Buffer.from(await response.arrayBuffer()));
  fs.renameSync(temporary, target);
  return target;
}

async function prefetchModels() { await Promise.all([model('scrfd'), model('arcface')]); }

const ACCEL = (process.env.FACE_ENGINE_ACCEL || 'auto').toLowerCase();
const options = { intraOpNumThreads: 1, graphOptimizationLevel: 'all', executionMode: 'sequential', logSeverityLevel: 3 };

function cudaProviders() {
  if (ACCEL === 'cpu') return null;
  if (ACCEL !== 'cuda' && !gpu.detectGPU()) return null; // auto: skip CUDA when no NVIDIA GPU was found
  const memLimitMb = Number(process.env.FACE_ENGINE_GPU_MEM_LIMIT_MB || 0);
  const cudaProvider = { name: 'cuda', deviceId: 0 };
  if (memLimitMb > 0) cudaProvider.cudaMemLimit = memLimitMb * 1024 * 1024;
  return [cudaProvider, 'cpu'];
}

let activeProvider = 'cpu'; // updated as sessions actually load, for /status

// Tries CUDA first (when requested/detected), then falls back to CPU-only if
// the CUDA execution provider can't actually load (missing/mismatched
// CUDA+cuDNN runtime libraries) — a broken GPU setup must never take the
// engine down, only make it as fast as the CPU-only build always was.
async function createSession(modelPath) {
  const providers = cudaProviders();
  if (providers) {
    try {
      const session = await ort.InferenceSession.create(modelPath, { ...options, executionProviders: providers });
      activeProvider = 'cuda';
      return session;
    } catch (error) { console.warn(`Face engine: CUDA execution provider unavailable (${error.message}), falling back to CPU for ${path.basename(modelPath)}`); }
  }
  activeProvider = 'cpu';
  return ort.InferenceSession.create(modelPath, { ...options, executionProviders: ['cpu'] });
}

function status() {
  return { accelMode: ACCEL, gpu: gpu.detectGPU(), activeProvider, modelsLoaded: !!sessions };
}

let sessions;
async function loadModels() {
  if (!sessions) sessions = Promise.all([
    createSession(await model('scrfd')),
    createSession(await model('arcface')),
  ]).then(([detector, recognizer]) => ({ detector, recognizer }));
  return sessions;
}

const DET_SIZE = Number(process.env.FACE_DET_SIZE || 1024);
const WORK_SIZE = Number(process.env.FACE_WORK_SIZE || 1600);
const DET_THRESHOLD = Number(process.env.FACE_DET_THRESHOLD || .40);
const MIN_FACE = Number(process.env.FACE_MIN_FACE || 20);
const STRIDES = [8, 16, 32];
const NUM_ANCHORS = 2;
const ARC_SIZE = 112;
const ARC_TEMPLATE = [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]];

async function prepare(buffer) {
  const { data, info } = await sharp(buffer).rotate().removeAlpha().resize({ width: WORK_SIZE, height: WORK_SIZE, fit: 'inside', withoutEnlargement: true }).raw().toBuffer({ resolveWithObject: true });
  return { rgb: data, width: info.width, height: info.height };
}

function overlap(a, b) {
  const left = Math.max(a[0], b[0]), top = Math.max(a[1], b[1]);
  const right = Math.min(a[0] + a[2], b[0] + b[2]), bottom = Math.min(a[1] + a[3], b[1] + b[3]);
  const inside = Math.max(0, right - left) * Math.max(0, bottom - top);
  return inside / (a[2] * a[3] + b[2] * b[3] - inside || 1);
}
function nms(items) {
  items.sort((a, b) => b.score - a.score);
  const kept = [];
  for (const item of items) if (!kept.some(other => overlap(item.box, other.box) > .4)) kept.push(item);
  return kept;
}

async function detect(rgb, width, height) {
  const { detector } = await loadModels();
  const scale = Math.min(DET_SIZE / width, DET_SIZE / height);
  const resized = await sharp(Buffer.from(rgb), { raw: { width, height, channels: 3 } }).resize(DET_SIZE, DET_SIZE, { fit: 'contain', position: 'left top', background: { r: 0, g: 0, b: 0 } }).raw().toBuffer();
  const plane = DET_SIZE * DET_SIZE;
  const input = new Float32Array(plane * 3);
  for (let i = 0; i < plane; i++) {
    input[i] = (resized[i * 3] - 127.5) / 128;
    input[plane + i] = (resized[i * 3 + 1] - 127.5) / 128;
    input[plane * 2 + i] = (resized[i * 3 + 2] - 127.5) / 128;
  }
  const output = await detector.run({ [detector.inputNames[0]]: new ort.Tensor('float32', input, [1, 3, DET_SIZE, DET_SIZE]) });
  const names = detector.outputNames, faces = [];
  for (let level = 0; level < 3; level++) {
    const stride = STRIDES[level], scores = output[names[level]].data, boxes = output[names[level + 3]].data, points = output[names[level + 6]].data;
    const gridWidth = Math.ceil(DET_SIZE / stride), gridHeight = Math.ceil(DET_SIZE / stride);
    let index = 0;
    for (let y = 0; y < gridHeight; y++) for (let x = 0; x < gridWidth; x++) for (let anchor = 0; anchor < NUM_ANCHORS; anchor++, index++) {
      if (scores[index] < DET_THRESHOLD) continue;
      const centerX = x * stride, centerY = y * stride, boxIndex = index * 4, pointIndex = index * 10;
      const box = [(centerX - boxes[boxIndex] * stride) / scale, (centerY - boxes[boxIndex + 1] * stride) / scale, (boxes[boxIndex] + boxes[boxIndex + 2]) * stride / scale, (boxes[boxIndex + 1] + boxes[boxIndex + 3]) * stride / scale];
      const kps = Array.from({ length: 5 }, (_, point) => [(centerX + points[pointIndex + point * 2] * stride) / scale, (centerY + points[pointIndex + point * 2 + 1] * stride) / scale]);
      faces.push({ score: scores[index], box, kps });
    }
  }
  return nms(faces);
}

function solveSimilarity(from, to) {
  const matrix = Array.from({ length: 4 }, () => [0, 0, 0, 0, 0]);
  const add = (row, value) => { for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) matrix[i][j] += row[i] * row[j]; for (let i = 0; i < 4; i++) matrix[i][4] += row[i] * value; };
  from.forEach(([x, y], index) => { const [targetX, targetY] = to[index]; add([x, -y, 1, 0], targetX); add([y, x, 0, 1], targetY); });
  for (let col = 0; col < 4; col++) {
    let pivot = col; for (let row = col + 1; row < 4; row++) if (Math.abs(matrix[row][col]) > Math.abs(matrix[pivot][col])) pivot = row;
    [matrix[col], matrix[pivot]] = [matrix[pivot], matrix[col]];
    for (let row = 0; row < 4; row++) if (row !== col) { const factor = matrix[row][col] / matrix[col][col]; for (let k = col; k <= 4; k++) matrix[row][k] -= factor * matrix[col][k]; }
  }
  return [matrix[0][4] / matrix[0][0], matrix[1][4] / matrix[1][1], matrix[2][4] / matrix[2][2], matrix[3][4] / matrix[3][3]];
}

function aligned(rgb, width, height, landmarks) {
  const [a, b, tx, ty] = solveSimilarity(ARC_TEMPLATE, landmarks), plane = ARC_SIZE * ARC_SIZE, result = new Float32Array(plane * 3);
  for (let outY = 0; outY < ARC_SIZE; outY++) for (let outX = 0; outX < ARC_SIZE; outX++) {
    const sourceX = a * outX - b * outY + tx, sourceY = b * outX + a * outY + ty, x = Math.floor(sourceX), y = Math.floor(sourceY), fx = sourceX - x, fy = sourceY - y;
    const x0 = Math.min(Math.max(x, 0), width - 1), x1 = Math.min(Math.max(x + 1, 0), width - 1), y0 = Math.min(Math.max(y, 0), height - 1), y1 = Math.min(Math.max(y + 1, 0), height - 1), offset = outY * ARC_SIZE + outX;
    for (let channel = 0; channel < 3; channel++) {
      const p00 = rgb[(y0 * width + x0) * 3 + channel], p10 = rgb[(y0 * width + x1) * 3 + channel], p01 = rgb[(y1 * width + x0) * 3 + channel], p11 = rgb[(y1 * width + x1) * 3 + channel];
      result[channel * plane + offset] = (p00 * (1 - fx) * (1 - fy) + p10 * fx * (1 - fy) + p01 * (1 - fx) * fy + p11 * fx * fy - 127.5) / 127.5;
    }
  }
  return result;
}

async function embed(input) {
  const { recognizer } = await loadModels();
  const output = await recognizer.run({ [recognizer.inputNames[0]]: new ort.Tensor('float32', input, [1, 3, ARC_SIZE, ARC_SIZE]) });
  const vector = output[recognizer.outputNames[0]].data;
  const norm = Math.sqrt(vector.reduce((total, value) => total + value * value, 0)) || 1;
  return Array.from(vector, value => value / norm);
}

async function describe(buffer) {
  const { rgb, width, height } = await prepare(buffer);
  const candidates = await detect(rgb, width, height);
  const described = [];
  for (const face of candidates) {
    if (face.box[2] < MIN_FACE || face.box[3] < MIN_FACE) continue;
    described.push({ score: Number(face.score.toFixed(4)), box: [face.box[0] / width, face.box[1] / height, (face.box[0] + face.box[2]) / width, (face.box[1] + face.box[3]) / height].map(value => Math.max(0, Math.min(1, value))), embedding: await embed(aligned(rgb, width, height, face.kps)) });
  }
  return described;
}

module.exports = { describe, prefetchModels, status };
