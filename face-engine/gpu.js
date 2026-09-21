/*
 * NVIDIA GPU/VRAM detection for the face engine. Fully opt-in: when
 * `nvidia-smi` is missing or reports nothing (any non-NVIDIA machine, or a
 * container without GPU passthrough), everything here returns null/false and
 * the engine behaves exactly as the CPU-only build always has.
 */
const { execFileSync } = require('child_process');

let cached;
function detectGPU() {
  if (cached !== undefined) return cached;
  try {
    const out = execFileSync('nvidia-smi', ['--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], { encoding: 'utf8', timeout: 10_000 });
    const [name, vramMb] = out.trim().split('\n')[0].split(',').map(s => s.trim());
    cached = vramMb ? { name, vramMb: Number(vramMb) } : null;
  } catch { cached = null; }
  return cached;
}

// Rough worker-count ceiling per VRAM tier: each worker holds its own CUDA
// context (~250-400MB overhead) plus the SCRFD/ArcFace weights (~150MB), so
// packing too many workers onto a small card causes CUDA OOM instead of
// speeding anything up.
const TIERS = [[8192, 8], [6144, 6], [4096, 4], [2048, 2]];
function workersForVram(vramMb) {
  if (!vramMb) return null;
  for (const [minMb, workers] of TIERS) if (vramMb >= minMb * 0.9) return workers;
  return 1; // detected GPU below 2GB: one CUDA worker, no point splitting further
}

module.exports = { detectGPU, workersForVram };
