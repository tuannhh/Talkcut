FROM node:24-bookworm-slim
WORKDIR /engine
COPY package*.json ./
RUN npm ci --omit=dev
COPY . ./
RUN useradd -m -u 10001 engine && mkdir -p /data/face-models && chown -R engine:engine /engine /data
USER engine
ENV NODE_ENV=production PORT=3210 FACE_MODEL_DIR=/data/face-models FACE_ENGINE_WORKERS=1
EXPOSE 3210
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD node -e "fetch('http://127.0.0.1:3210/health').then(r=>{if(!r.ok)process.exit(1)})"
CMD ["node", "server.js"]
