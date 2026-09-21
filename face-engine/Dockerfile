FROM node:24-bookworm-slim AS base
# Minimal NVIDIA CUDA runtime libraries — only what onnxruntime-node's CUDA
# execution provider actually links against (verified with `ldd` against the
# real onnxruntime_binding.node + libonnxruntime_providers_cuda.so): cudart,
# cublas(Lt), cufft, curand, cudnn. This is a small fraction of the full
# `nvidia/cuda:*-cudnn-runtime` base image (which also bundles NCCL, cuSOLVER,
# cuSPARSE, NPP, nvJPEG, etc. that onnxruntime never touches), so machines
# without an NVIDIA GPU don't pay for a multi-GB image they'll never use the
# CUDA path of. If no NVIDIA driver is present at runtime, the CUDA provider
# simply fails to load and face.js falls back to CPU (see face.js).
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates wget gnupg \
    && wget -q https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb \
    && dpkg -i cuda-keyring_1.1-1_all.deb && rm cuda-keyring_1.1-1_all.deb \
    && apt-get update && apt-get install -y --no-install-recommends \
       cuda-cudart-12-6 libcublas-12-6 libcufft-12-6 libcurand-12-6 libcudnn9-cuda-12 \
    && apt-get purge -y wget gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
ENV LD_LIBRARY_PATH=/usr/local/cuda/targets/x86_64-linux/lib

# Create the user and switch to it *before* installing/copying anything, so
# npm ci's ~750MB of output (onnxruntime-node's bundled CUDA .so files are
# most of that) is written already owned by `engine`. A `chown -R` done
# afterwards would force overlayfs to copy up every one of those files into
# a new layer, silently duplicating ~600MB in the final image for no reason.
RUN useradd -m -u 10001 engine && mkdir -p /data/face-models && chown -R engine:engine /data
WORKDIR /engine
RUN chown engine:engine /engine
USER engine
COPY --chown=engine:engine package*.json ./
RUN npm ci --omit=dev
COPY --chown=engine:engine . ./
ENV NODE_ENV=production PORT=3210 FACE_MODEL_DIR=/data/face-models FACE_ENGINE_ACCEL=auto
EXPOSE 3210
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD node -e "fetch('http://127.0.0.1:3210/health').then(r=>{if(!r.ok)process.exit(1)})"
CMD ["node", "server.js"]
