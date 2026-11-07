#!/bin/bash
# Compila whisper.cpp en ~/.cache/whisper.cpp y descarga el modelo large-v3-turbo (~550 MB) en ~/.cache/whisper-models.
# Apple Silicon: con Metal (GPU). Intel: sin Metal, con el SDK explícito (Homebrew ya no publica binarios para Intel).
set -e
D="${1:-$HOME/.cache/whisper.cpp}"
[ -d "$D" ] || git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$D"
cd "$D"
if [ "$(uname -m)" = "arm64" ]; then
  cmake -B build -DCMAKE_BUILD_TYPE=Release >/dev/null
else
  SDK=$(xcrun --show-sdk-path)
  SDKROOT=$SDK cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_METAL=OFF -DCMAKE_OSX_SYSROOT=$SDK \
    -DCMAKE_CXX_FLAGS="-isystem $SDK/usr/include/c++/v1" >/dev/null
fi
cmake --build build -j "$(sysctl -n hw.ncpu)" --target whisper-cli >/dev/null
M=$HOME/.cache/whisper-models; mkdir -p "$M"
[ -f "$M/ggml-large-v3-turbo-q5_0.bin" ] || curl -L -o "$M/ggml-large-v3-turbo-q5_0.bin" \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin
echo "whisper-cli: $D/build/bin/whisper-cli  (usar con DYLD_LIBRARY_PATH=$D/build/bin)"
