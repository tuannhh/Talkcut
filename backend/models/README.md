# Bundled visual models

`face_recognition_sface_2021dec.onnx` is the official OpenCV Zoo SFace model,
downloaded from `opencv/opencv_zoo` on 2026-09-09.

- Source: https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- License: Apache-2.0 (see the upstream model directory).
- SHA-256: `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79`

TalkCut uses it only to compare the user-selected portrait with detected faces
inside the current source video. It does not make a cross-video identity index,
assign a name, or infer who is speaking from the embedding.
